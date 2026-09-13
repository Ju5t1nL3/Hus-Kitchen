"""Vertical-slice tests for the single-writer application coordinator."""

import unittest
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from deskpet.adapters.config_loader import load
from deskpet.adapters.fakes import (
    FakeClock,
    FakeDeviceLink,
    FakeEventStore,
    FakeKeyboardTracker,
)
from deskpet.app.application import Application
from deskpet.core.events import (
    BreakSkipped,
    EndReason,
    FocusRewardGranted,
    FocusSessionCompleted,
    FocusSessionEnded,
    FocusSessionPaused,
    FocusSessionResumed,
    FocusSessionStarted,
    ItemPurchasedAndFed,
    UncommittedEvent,
)
from deskpet.core.models import (
    ButtonId,
    ClockReading,
    Feedback,
    Gesture,
    PublishStatus,
    Screen,
    SessionStatus,
)
from deskpet.core.ports import AppendResult, EventStoreError
from deskpet.core.views import (
    AnimationCue,
    ButtonInput,
    ConnectionChanged,
    DeviceReady,
    RenderSnapshot,
    Tick,
)

CONFIG_PATH = Path(__file__).parents[2] / "config.yaml"
BUTTONS = (ButtonId(1), ButtonId(2), ButtonId(3))
NOW = ClockReading(datetime(2026, 9, 13, 14, 0, tzinfo=UTC), 1_000, False)


class SequentialUuids:
    def __init__(self) -> None:
        self._next = 1

    def __call__(self) -> UUID:
        value = UUID(int=self._next)
        self._next += 1
        return value


class TracedStore(FakeEventStore):
    def __init__(self, trace: list[str]) -> None:
        super().__init__()
        self._trace = trace

    def append(self, event: UncommittedEvent) -> AppendResult:
        self._trace.append(f"append:{event.draft.event_type}")
        return super().append(event)


class TracedDevice(FakeDeviceLink):
    def __init__(self, trace: list[str]) -> None:
        super().__init__()
        self._trace = trace

    def publish(self, view: RenderSnapshot, revision: int) -> PublishStatus:
        self._trace.append(f"publish:{view.screen.value}")
        return super().publish(view, revision)

    def animate(self, cue: AnimationCue) -> PublishStatus:
        self._trace.append(f"animate:{cue.name.value}")
        return super().animate(cue)


class FailNextAppendStore(FakeEventStore):
    def __init__(self) -> None:
        super().__init__()
        self.fail_next_append = False

    def append(self, event: UncommittedEvent) -> AppendResult:
        if self.fail_next_append:
            self.fail_next_append = False
            raise EventStoreError("injected append failure")
        return super().append(event)


class ApplicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = FakeClock(NOW)
        self.store = FakeEventStore()
        self.device = FakeDeviceLink()
        self.keyboard = FakeKeyboardTracker()
        self.app = Application(
            self.store,
            self.device,
            self.clock,
            load(CONFIG_PATH),
            uuid_factory=SequentialUuids(),
            keyboard_tracker=self.keyboard,
        )
        self.app.start()
        self.addCleanup(self.app.stop)
        self.connect()

    def connect(self) -> None:
        self.app.handle(ConnectionChanged("connection-1", True), self.clock.read())
        self.app.handle(
            DeviceReady("connection-1", "boot-1", BUTTONS, "emotions_v1"),
            self.clock.read(),
        )

    def press(self, button: int, seq: int) -> None:
        self.app.handle(
            ButtonInput(
                "connection-1",
                "boot-1",
                seq,
                self.app.runtime.control_epoch,
                ButtonId(button),
                Gesture.PRESS,
                self.clock.read(),
            ),
            self.clock.read(),
        )

    def hold(self, button: int, seq: int) -> None:
        self.app.handle(
            ButtonInput(
                "connection-1",
                "boot-1",
                seq,
                self.app.runtime.control_epoch,
                ButtonId(button),
                Gesture.HOLD,
                self.clock.read(),
            ),
            self.clock.read(),
        )

    def start_focus(self) -> None:
        self.press(2, 1)
        self.press(2, 2)

    def test_feed_menu_buys_both_items_and_spends_yarn(self) -> None:
        self.clock.advance(300_000)
        self.press(1, 1)
        self.assertIs(self.app.runtime.screen, Screen.FEED)
        self.assertEqual(
            [label.label for label in self.device.published[-1].view.buttons],
            ["Jollof 3Y", "Coffee 2Y", "Back"],
        )
        self.press(2, 2)
        self.assertIs(self.app.runtime.screen, Screen.HOME)
        assert self.app.state.progression is not None
        self.assertEqual(self.app.state.progression.yarn_balance, 8)

        self.clock.advance(300_000)
        self.press(1, 3)
        self.press(1, 4)

        assert self.app.state.progression is not None
        self.assertEqual(self.app.state.progression.yarn_balance, 5)
        self.assertEqual(self.device.published[-1].view.mood.value, "happy")

    def test_settings_opt_in_and_keyboard_bonus_exclude_paused_presses(self) -> None:
        self.hold(1, 1)
        self.assertIs(self.app.runtime.screen, Screen.SETTINGS)
        settings = self.device.published[-1].view.settings
        assert settings is not None
        self.assertFalse(settings.keyboard_enabled)
        self.assertFalse(settings.camera_available)

        self.press(2, 2)
        self.assertTrue(self.app.state.keyboard_tracking_enabled)
        self.press(1, 3)
        self.press(2, 4)
        self.assertFalse(self.app.state.camera_tracking_enabled)
        self.press(3, 5)

        self.press(2, 6)
        self.press(2, 7)
        self.assertTrue(self.keyboard.capturing)
        self.keyboard.add_presses(499)
        self.press(2, 8)
        self.assertFalse(self.keyboard.capturing)
        self.keyboard.add_presses(1_000)
        self.press(2, 9)
        self.keyboard.add_presses(1)
        self.clock.advance(1_500_000)
        self.app.handle(Tick(self.clock.read()), self.clock.read())

        reward = self.store.events[-1].event.draft
        assert isinstance(reward, FocusRewardGranted)
        self.assertEqual(reward.keyboard_keypresses, 500)
        self.assertEqual(reward.keyboard_yarn, 1)
        earned = self.device.published[-1].view.earned_rewards
        assert earned is not None
        self.assertEqual(earned.yarn, 4)

    def test_insufficient_yarn_does_not_append_or_animate(self) -> None:
        for index in range(5):
            self.clock.advance(300_000)
            self.press(1, index * 2 + 1)
            self.press(2, index * 2 + 2)
        assert self.app.state.progression is not None
        self.assertEqual(self.app.state.progression.yarn_balance, 0)
        event_count = len(self.store.events)
        cue_count = len(self.device.animations)

        self.clock.advance(300_000)
        self.press(1, 11)
        self.assertFalse(self.device.published[-1].view.buttons[1].enabled)
        self.press(2, 12)

        self.assertEqual(len(self.store.events), event_count)
        self.assertEqual(len(self.device.animations), cue_count)
        self.assertIs(self.app.runtime.screen, Screen.FEED)

    def test_home_setup_focus_vertical_slice_uses_three_button_labels(self) -> None:
        self.assertEqual(
            [label.label for label in self.device.published[-1].view.buttons],
            ["Feed", "Focus", "-"],
        )

        self.press(2, 1)
        self.assertIs(self.app.runtime.screen, Screen.SETUP)
        self.assertEqual(
            [label.label for label in self.device.published[-1].view.buttons],
            ["Up", "Set", "Back"],
        )
        self.press(2, 2)

        self.assertIs(self.app.runtime.screen, Screen.FOCUS)
        self.assertIsInstance(self.store.events[-1].event.draft, FocusSessionStarted)
        self.assertEqual(
            [label.label for label in self.device.published[-1].view.buttons],
            ["Time", "Pause", "End"],
        )

    def test_five_pets_clear_sad_then_reveal_hunger_before_feeding(self) -> None:
        self.start_focus()
        self.clock.advance(60_000)
        self.press(3, 3)
        self.assertTrue(self.app.state.needs_comfort)
        self.assertEqual(self.device.published[-1].view.mood.value, "sad")
        self.assertEqual(
            [label.label for label in self.device.published[-1].view.buttons],
            ["Feed", "Focus", "Pet"],
        )

        self.clock.advance(240_000)
        for sequence in range(4, 8):
            self.press(3, sequence)
            self.assertTrue(self.app.state.needs_comfort)
        self.assertEqual(self.app.runtime.sad_pet_count, 4)
        self.press(3, 8)

        self.assertFalse(self.app.state.needs_comfort)
        self.assertEqual(self.app.runtime.sad_pet_count, 0)
        self.assertEqual(self.device.published[-1].view.mood.value, "hungry")
        self.press(1, 9)
        self.press(2, 10)
        self.assertEqual(self.device.published[-1].view.mood.value, "happy")

    def test_due_completion_precedes_and_invalidates_old_end_press(self) -> None:
        self.start_focus()
        old_epoch = self.app.runtime.control_epoch
        self.clock.advance(1_500_000)
        old_end = ButtonInput(
            "connection-1",
            "boot-1",
            3,
            old_epoch,
            ButtonId(3),
            Gesture.PRESS,
            self.clock.read(),
        )

        self.app.handle(old_end, self.clock.read())

        self.assertIs(self.app.runtime.screen, Screen.BREAK_OFFER)
        self.assertIsInstance(self.store.events[-2].event.draft, FocusSessionCompleted)
        self.assertIsInstance(self.store.events[-1].event.draft, FocusRewardGranted)
        self.assertEqual(len(self.store.events), 5)
        self.assertEqual(len(self.device.animations), 1)
        assert self.app.state.progression is not None
        self.assertEqual(self.app.state.progression.total_xp, 75)
        self.assertEqual(self.app.state.progression.level, 2)
        self.assertEqual(self.app.state.progression.yarn_balance, 13)
        self.assertEqual(self.app.runtime.focus_chain_count, 1)
        rewards = self.device.published[-1].view.earned_rewards
        assert rewards is not None
        self.assertEqual((rewards.xp, rewards.yarn), (75, 3))

    def test_focus_pause_resume_and_clock_reveal_are_runtime_driven(self) -> None:
        self.start_focus()
        self.clock.advance(12_000)
        self.press(2, 3)
        session = self.app.state.active_session
        self.assertIsNotNone(session)
        assert session is not None
        self.assertIs(session.status, SessionStatus.PAUSED)
        self.assertIsInstance(self.store.events[-1].event.draft, FocusSessionPaused)

        self.press(1, 4)
        self.assertEqual(self.device.published[-1].view.clock_text, "09:00")
        self.assertIsNone(self.device.published[-1].view.timer_seconds)
        reveal_epoch = self.app.runtime.control_epoch
        self.clock.advance(5_000)
        self.app.handle(Tick(self.clock.read()), self.clock.read())
        self.assertIsNone(self.device.published[-1].view.clock_text)
        self.assertEqual(self.device.published[-1].view.timer_seconds, 1_488)
        self.assertEqual(self.app.runtime.control_epoch, reveal_epoch)

        self.press(2, 5)
        session = self.app.state.active_session
        self.assertIsNotNone(session)
        assert session is not None
        self.assertIs(session.status, SessionStatus.RUNNING)
        self.assertIsInstance(self.store.events[-1].event.draft, FocusSessionResumed)

    def test_again_commits_break_skip_then_focus_start_and_renders_once(self) -> None:
        self.start_focus()
        self.clock.advance(1_500_000)
        self.app.handle(Tick(self.clock.read()), self.clock.read())
        renders_before = len(self.device.published)

        self.press(2, 3)

        self.assertIs(self.app.runtime.screen, Screen.FOCUS)
        self.assertIsInstance(self.store.events[-2].event.draft, BreakSkipped)
        self.assertIsInstance(self.store.events[-1].event.draft, FocusSessionStarted)
        self.assertEqual(len(self.device.published), renders_before + 1)
        self.assertEqual(self.app.runtime.focus_chain_count, 1)
        self.assertIsNone(self.app.runtime.last_earned_xp)

        self.clock.advance(1_500_000)
        self.app.handle(Tick(self.clock.read()), self.clock.read())

        reward = self.store.events[-1].event.draft
        self.assertIsInstance(reward, FocusRewardGranted)
        assert isinstance(reward, FocusRewardGranted)
        self.assertEqual(reward.chain_number, 2)
        self.assertEqual((reward.base_xp + reward.chain_xp), 86)
        self.assertEqual((reward.base_yarn + reward.chain_yarn), 4)
        self.assertEqual(self.app.runtime.focus_chain_count, 2)

        self.press(3, 4)
        self.assertIs(self.app.runtime.screen, Screen.HOME)
        self.assertEqual(self.app.runtime.focus_chain_count, 0)

    def test_reconnect_keeps_render_revisions_increasing(self) -> None:
        previous_revision = self.device.published[-1].revision
        self.app.handle(ConnectionChanged("connection-1", False), self.clock.read())
        self.app.handle(ConnectionChanged("connection-2", True), self.clock.read())
        self.app.handle(
            DeviceReady("connection-2", "boot-2", BUTTONS, "emotions_v1"),
            self.clock.read(),
        )

        self.assertGreater(self.device.published[-1].revision, previous_revision)

    def test_detected_sleep_neutrally_ends_from_saved_elapsed(self) -> None:
        self.start_focus()
        self.clock.advance(12_000)
        self.press(2, 3)
        self.clock.advance(60_000, resumed=True)

        self.app.handle(Tick(self.clock.read()), self.clock.read())

        ended = self.store.events[-1].event.draft
        self.assertIsInstance(ended, FocusSessionEnded)
        assert isinstance(ended, FocusSessionEnded)
        self.assertIs(ended.reason, EndReason.SUSPEND)
        self.assertEqual(ended.active_ms, 12_000)
        self.assertIsNone(ended.reaction)
        self.assertIsNone(self.app.state.active_session)

    def test_shutdown_records_live_elapsed_neutrally_before_close(self) -> None:
        self.start_focus()
        self.clock.advance(12_000)

        self.app.stop()

        ended = self.store.events[-1].event.draft
        self.assertIsInstance(ended, FocusSessionEnded)
        assert isinstance(ended, FocusSessionEnded)
        self.assertIs(ended.reason, EndReason.APP_SHUTDOWN)
        self.assertEqual(ended.active_ms, 12_000)
        self.assertIsNone(ended.reaction)
        self.assertTrue(self.device.stopped)
        self.assertTrue(self.store.closed)


class RecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load(CONFIG_PATH)
        self.clock = FakeClock(NOW)

    def _start_connected_focus(self) -> tuple[Application, FakeEventStore]:
        store = FakeEventStore()
        app = Application(
            store,
            FakeDeviceLink(),
            self.clock,
            self.config,
            uuid_factory=SequentialUuids(),
        )
        app.start()
        app.handle(ConnectionChanged("connection-1", True), self.clock.read())
        app.handle(
            DeviceReady("connection-1", "boot-1", BUTTONS, "emotions_v1"),
            self.clock.read(),
        )
        for seq in (1, 2):
            app.handle(
                ButtonInput(
                    "connection-1",
                    "boot-1",
                    seq,
                    app.runtime.control_epoch,
                    ButtonId(2),
                    Gesture.PRESS,
                    self.clock.read(),
                ),
                self.clock.read(),
            )
        return app, store

    def test_restart_ends_unfinished_session_without_animation(self) -> None:
        _original, original_store = self._start_connected_focus()
        persisted = original_store.events

        restarted_store = FakeEventStore(persisted)
        restarted_device = FakeDeviceLink()
        restarted = Application(
            restarted_store,
            restarted_device,
            self.clock,
            self.config,
            uuid_factory=SequentialUuids(),
        )
        restarted.start()
        self.addCleanup(restarted.stop)

        ended = restarted_store.events[-1].event.draft
        self.assertIsInstance(ended, FocusSessionEnded)
        assert isinstance(ended, FocusSessionEnded)
        self.assertIs(ended.reason, EndReason.APP_RESTART)
        self.assertEqual(ended.active_ms, 0)
        self.assertIsNone(ended.reaction)
        self.assertIsNone(restarted.state.active_session)
        self.assertIs(restarted.runtime.screen, Screen.HOME)
        self.assertEqual(restarted_device.animations, [])

    def test_restart_preserves_pending_break_offer(self) -> None:
        original, original_store = self._start_connected_focus()
        self.clock.advance(25 * 60 * 1_000)
        original.handle(Tick(self.clock.read()), self.clock.read())
        persisted = original_store.events

        restarted_device = FakeDeviceLink()
        restarted = Application(
            FakeEventStore(persisted),
            restarted_device,
            self.clock,
            self.config,
        )
        restarted.start()
        self.addCleanup(restarted.stop)

        self.assertIsNotNone(restarted.state.pending_break)
        self.assertIs(restarted.runtime.screen, Screen.BREAK_OFFER)
        self.assertEqual(restarted_device.animations, [])

    def test_storage_failure_freezes_then_replays_and_ends_neutrally(self) -> None:
        store = FailNextAppendStore()
        device = FakeDeviceLink()
        app = Application(
            store,
            device,
            self.clock,
            self.config,
            uuid_factory=SequentialUuids(),
        )
        app.start()
        self.addCleanup(app.stop)
        app.handle(ConnectionChanged("connection-1", True), self.clock.read())
        app.handle(
            DeviceReady("connection-1", "boot-1", BUTTONS, "emotions_v1"),
            self.clock.read(),
        )
        for seq in (1, 2):
            app.handle(
                ButtonInput(
                    "connection-1",
                    "boot-1",
                    seq,
                    app.runtime.control_epoch,
                    ButtonId(2),
                    Gesture.PRESS,
                    self.clock.read(),
                ),
                self.clock.read(),
            )
        self.clock.advance(12_000)
        store.fail_next_append = True
        app.handle(
            ButtonInput(
                "connection-1",
                "boot-1",
                3,
                app.runtime.control_epoch,
                ButtonId(2),
                Gesture.PRESS,
                self.clock.read(),
            ),
            self.clock.read(),
        )

        self.assertIs(app.runtime.feedback, Feedback.STORAGE_ERROR)
        self.assertIs(device.published[-1].view.feedback, Feedback.STORAGE_ERROR)
        self.assertIsNotNone(app.state.active_session)

        app.handle(Tick(self.clock.read()), self.clock.read())

        ended = store.events[-1].event.draft
        self.assertIsInstance(ended, FocusSessionEnded)
        assert isinstance(ended, FocusSessionEnded)
        self.assertIs(ended.reason, EndReason.STORAGE_RECOVERY)
        self.assertEqual(ended.active_ms, 0)
        self.assertIsNone(app.runtime.feedback)
        self.assertIsNone(app.state.active_session)
        self.assertEqual(device.animations, [])


class CommitOrderingTests(unittest.TestCase):
    def test_feed_is_committed_before_render_and_animation(self) -> None:
        trace: list[str] = []
        clock = FakeClock(NOW)
        store = TracedStore(trace)
        device = TracedDevice(trace)
        app = Application(
            store,
            device,
            clock,
            load(CONFIG_PATH),
            uuid_factory=SequentialUuids(),
        )
        app.start()
        self.addCleanup(app.stop)
        app.handle(ConnectionChanged("connection-1", True), clock.read())
        app.handle(
            DeviceReady("connection-1", "boot-1", BUTTONS, "emotions_v1"),
            clock.read(),
        )
        trace.clear()
        clock.advance(300_000)

        app.handle(
            ButtonInput(
                "connection-1",
                "boot-1",
                1,
                app.runtime.control_epoch,
                ButtonId(1),
                Gesture.PRESS,
                clock.read(),
            ),
            clock.read(),
        )
        app.handle(
            ButtonInput(
                "connection-1",
                "boot-1",
                2,
                app.runtime.control_epoch,
                ButtonId(1),
                Gesture.PRESS,
                clock.read(),
            ),
            clock.read(),
        )

        self.assertIsInstance(store.events[-1].event.draft, ItemPurchasedAndFed)
        self.assertEqual(
            trace,
            [
                "publish:feed",
                "append:item_purchased_and_fed",
                "publish:home",
                "animate:feed",
            ],
        )


if __name__ == "__main__":
    unittest.main()
