"""Vertical-slice tests for the single-writer application coordinator."""

import unittest
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from deskpet.adapters.config_loader import load
from deskpet.adapters.fakes import FakeClock, FakeDeviceLink, FakeEventStore
from deskpet.app.application import Application
from deskpet.core.events import (
    BreakSkipped,
    FocusSessionCompleted,
    FocusSessionPaused,
    FocusSessionResumed,
    FocusSessionStarted,
    PetFed,
    UncommittedEvent,
)
from deskpet.core.models import (
    ButtonId,
    ClockReading,
    Gesture,
    PublishStatus,
    Screen,
    SessionStatus,
)
from deskpet.core.ports import AppendResult
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


class ApplicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = FakeClock(NOW)
        self.store = FakeEventStore()
        self.device = FakeDeviceLink()
        self.app = Application(
            self.store,
            self.device,
            self.clock,
            load(CONFIG_PATH),
            uuid_factory=SequentialUuids(),
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

    def start_focus(self) -> None:
        self.press(2, 1)
        self.press(2, 2)

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
        self.assertIsInstance(self.store.events[-1].event.draft, FocusSessionCompleted)
        self.assertEqual(len(self.store.events), 3)
        self.assertEqual(len(self.device.animations), 1)

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

    def test_reconnect_keeps_render_revisions_increasing(self) -> None:
        previous_revision = self.device.published[-1].revision
        self.app.handle(ConnectionChanged("connection-1", False), self.clock.read())
        self.app.handle(ConnectionChanged("connection-2", True), self.clock.read())
        self.app.handle(
            DeviceReady("connection-2", "boot-2", BUTTONS, "emotions_v1"),
            self.clock.read(),
        )

        self.assertGreater(self.device.published[-1].revision, previous_revision)


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

        self.assertIsInstance(store.events[-1].event.draft, PetFed)
        self.assertEqual(trace, ["append:pet_fed", "publish:home", "animate:feed"])


if __name__ == "__main__":
    unittest.main()
