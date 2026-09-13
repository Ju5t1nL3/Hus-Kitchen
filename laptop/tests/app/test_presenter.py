"""Presenter snapshots must match docs/serial_protocol.md's render fixtures.

Each test below reconstructs the GameState/RuntimeState/sample/clock that would
produce one of the independent screen fixtures in that document, and asserts
presenter.build's RenderSnapshot has exactly those field values. The
bindings/actions passed in are a fixture-only stand-in for M11's real
config-driven bindings loader; they only need to reproduce these labels. This
reflects the three-physical-button control layout: Home and the break-running
screen bind only two of the three advertised buttons, the rest bind all three.
"""

import unittest
from datetime import UTC, datetime
from uuid import uuid4

from deskpet.app.presenter import PresenterConfig, build, on_commit
from deskpet.core.commands import (
    ActionId,
    BackHome,
    ConfirmFocus,
    CycleDuration,
    CycleDurationBack,
    EndCurrent,
    FeedDefault,
    OpenSetup,
    PauseCurrent,
    PetOnce,
    RestartFocus,
    ResumeCurrent,
    ShowTime,
    SkipBreakIntent,
    StartBreakIntent,
)
from deskpet.core.events import (
    BreakSessionStarted,
    DomainEvent,
    EventDraft,
    EventSource,
    FocusSessionCompleted,
    FocusSessionStarted,
    PetComforted,
    PetFed,
    SoundPreferenceChanged,
    UncommittedEvent,
)
from deskpet.core.models import (
    BreakOffer,
    BreakTerms,
    ButtonId,
    ClockReading,
    FocusTerms,
    FoodDefinition,
    GameState,
    Gesture,
    Reaction,
    ReactionMood,
    RuntimeState,
    Screen,
    Session,
    SessionKind,
    SessionStatus,
    TimerSample,
)
from deskpet.core.views import ActionDefinition, ButtonLabel, ControlContext
from deskpet.features.timers import BreakPolicy

CONFIG = PresenterConfig(clock_timezone="UTC", break_policy=BreakPolicy())
DEVICE_BUTTONS = (ButtonId(1), ButtonId(2), ButtonId(3), ButtonId(4))

ACTIONS = {
    ActionId.FEED_DEFAULT: ActionDefinition(
        id=ActionId.FEED_DEFAULT,
        label="Feed",
        intent=FeedDefault(),
        available=lambda _: True,
    ),
    ActionId.OPEN_SETUP: ActionDefinition(
        id=ActionId.OPEN_SETUP,
        label="Focus",
        intent=OpenSetup(),
        available=lambda _: True,
    ),
    ActionId.CYCLE_DURATION: ActionDefinition(
        id=ActionId.CYCLE_DURATION,
        label="Up",
        intent=CycleDuration(),
        available=lambda _: True,
    ),
    ActionId.CYCLE_DURATION_BACK: ActionDefinition(
        id=ActionId.CYCLE_DURATION_BACK,
        label="Down",
        intent=CycleDurationBack(),
        available=lambda _: True,
    ),
    ActionId.PET: ActionDefinition(
        id=ActionId.PET,
        label="Pet",
        intent=PetOnce(),
        available=lambda _: True,
    ),
    ActionId.CONFIRM_FOCUS: ActionDefinition(
        id=ActionId.CONFIRM_FOCUS,
        label="Set",
        intent=ConfirmFocus(),
        available=lambda _: True,
    ),
    ActionId.BACK_HOME: ActionDefinition(
        id=ActionId.BACK_HOME,
        label="Back",
        intent=BackHome(),
        available=lambda _: True,
    ),
    ActionId.SHOW_TIME: ActionDefinition(
        id=ActionId.SHOW_TIME,
        label="Time",
        intent=ShowTime(),
        available=lambda _: True,
    ),
    ActionId.END_CURRENT: ActionDefinition(
        id=ActionId.END_CURRENT,
        label="End",
        intent=EndCurrent(),
        available=lambda _: True,
    ),
    ActionId.PAUSE_CURRENT: ActionDefinition(
        id=ActionId.PAUSE_CURRENT,
        label="Pause",
        intent=PauseCurrent(),
        available=lambda _: True,
    ),
    ActionId.RESUME_CURRENT: ActionDefinition(
        id=ActionId.RESUME_CURRENT,
        label="Resume",
        intent=ResumeCurrent(),
        available=lambda _: True,
    ),
    ActionId.SKIP_BREAK: ActionDefinition(
        id=ActionId.SKIP_BREAK,
        label="Home",
        intent=SkipBreakIntent(),
        available=lambda _: True,
    ),
    ActionId.START_BREAK: ActionDefinition(
        id=ActionId.START_BREAK,
        label="Break",
        intent=StartBreakIntent(),
        available=lambda _: True,
    ),
    ActionId.RESTART_FOCUS: ActionDefinition(
        id=ActionId.RESTART_FOCUS,
        label="Again",
        intent=RestartFocus(),
        available=lambda state: state.last_focus_minutes is not None,
    ),
    ActionId.END_BREAK: ActionDefinition(
        id=ActionId.END_BREAK,
        label="Home",
        intent=EndCurrent(),
        available=lambda _: True,
    ),
}

BINDINGS = {
    (ControlContext.HOME, ButtonId(1), Gesture.PRESS): ActionId.FEED_DEFAULT,
    (ControlContext.HOME, ButtonId(2), Gesture.PRESS): ActionId.OPEN_SETUP,
    (ControlContext.HOME, ButtonId(3), Gesture.PRESS): ActionId.PET,
    (ControlContext.SETUP, ButtonId(1), Gesture.PRESS): ActionId.CYCLE_DURATION,
    (ControlContext.SETUP, ButtonId(2), Gesture.PRESS): ActionId.CONFIRM_FOCUS,
    (ControlContext.SETUP, ButtonId(3), Gesture.PRESS): ActionId.CYCLE_DURATION_BACK,
    (ControlContext.SETUP, ButtonId(4), Gesture.PRESS): ActionId.BACK_HOME,
    (ControlContext.FOCUS_RUNNING, ButtonId(1), Gesture.PRESS): ActionId.SHOW_TIME,
    (ControlContext.FOCUS_RUNNING, ButtonId(2), Gesture.PRESS): ActionId.PAUSE_CURRENT,
    (ControlContext.FOCUS_RUNNING, ButtonId(3), Gesture.PRESS): ActionId.END_CURRENT,
    (ControlContext.FOCUS_PAUSED, ButtonId(1), Gesture.PRESS): ActionId.SHOW_TIME,
    (ControlContext.FOCUS_PAUSED, ButtonId(2), Gesture.PRESS): ActionId.RESUME_CURRENT,
    (ControlContext.FOCUS_PAUSED, ButtonId(3), Gesture.PRESS): ActionId.END_CURRENT,
    (ControlContext.BREAK_OFFER, ButtonId(1), Gesture.PRESS): ActionId.START_BREAK,
    (ControlContext.BREAK_OFFER, ButtonId(2), Gesture.PRESS): ActionId.RESTART_FOCUS,
    (ControlContext.BREAK_OFFER, ButtonId(3), Gesture.PRESS): ActionId.SKIP_BREAK,
    (ControlContext.BREAK_RUNNING, ButtonId(1), Gesture.PRESS): ActionId.RESTART_FOCUS,
    (ControlContext.BREAK_RUNNING, ButtonId(2), Gesture.PRESS): ActionId.END_BREAK,
}


def _clock(hour: int, minute: int, monotonic_ms: int = 0) -> ClockReading:
    return ClockReading(
        datetime(2026, 9, 13, hour, minute, tzinfo=UTC), monotonic_ms, False
    )


def _runtime(
    screen: Screen,
    epoch: int,
    *,
    clock_reveal_until_mono_ms: int | None = None,
) -> RuntimeState:
    return RuntimeState(
        screen=screen,
        selected_focus_minutes=25,
        run_anchor_mono_ms=None,
        previous_clock=None,
        control_epoch=epoch,
        connection_id=None,
        boot_id=None,
        clock_reveal_until_mono_ms=clock_reveal_until_mono_ms,
    )


class PresenterFixtureTests(unittest.TestCase):
    def test_home_screen_matches_fixture(self) -> None:
        state = GameState(user_id="u1", pet_id="p1")
        snapshot = build(
            state,
            _runtime(Screen.HOME, 1),
            None,
            _clock(14, 32),
            CONFIG,
            BINDINGS,
            ACTIONS,
            DEVICE_BUTTONS,
        )
        self.assertEqual(snapshot.screen, Screen.HOME)
        self.assertEqual(snapshot.control_epoch, 1)
        self.assertEqual(snapshot.mood, "idle")
        self.assertEqual(snapshot.clock_text, "14:32")
        self.assertIsNone(snapshot.timer_seconds)
        self.assertFalse(snapshot.paused)
        self.assertIsNone(snapshot.focus_minutes)
        self.assertIsNone(snapshot.break_minutes)
        self.assertEqual(
            snapshot.buttons,
            (
                ButtonLabel(button=ButtonId(1), label="Feed", enabled=True),
                ButtonLabel(button=ButtonId(2), label="Focus", enabled=True),
                ButtonLabel(button=ButtonId(3), label="Pet", enabled=True),
                ButtonLabel(button=ButtonId(4), label="-", enabled=False),
            ),
        )
        self.assertIsNone(snapshot.feedback)

    def test_setup_screen_matches_fixture(self) -> None:
        state = GameState(user_id="u1", pet_id="p1")
        snapshot = build(
            state,
            _runtime(Screen.SETUP, 2),
            None,
            _clock(14, 32),
            CONFIG,
            BINDINGS,
            ACTIONS,
            DEVICE_BUTTONS,
        )
        self.assertEqual(snapshot.mood, "idle")
        self.assertIsNone(snapshot.clock_text)
        self.assertEqual(snapshot.focus_minutes, 25)
        self.assertEqual(snapshot.break_minutes, 5)
        self.assertEqual(
            [label.label for label in snapshot.buttons], ["Up", "Set", "Down", "Back"]
        )

    def test_focus_running_matches_fixture(self) -> None:
        session = Session(
            id="s1",
            kind=SessionKind.FOCUS,
            terms=FocusTerms(1500, 300, 60_000, 30, 30, "UTC"),
            status=SessionStatus.RUNNING,
            committed_active_ms=0,
        )
        state = GameState(user_id="u1", pet_id="p1", active_session=session)
        sample = TimerSample(
            session_id="s1", active_ms=1000, remaining_seconds=1499, due=False
        )
        snapshot = build(
            state,
            _runtime(Screen.FOCUS, 3),
            sample,
            _clock(14, 32),
            CONFIG,
            BINDINGS,
            ACTIONS,
            DEVICE_BUTTONS,
        )
        self.assertEqual(snapshot.mood, "working_neutral")
        self.assertEqual(snapshot.timer_seconds, 1499)
        self.assertFalse(snapshot.paused)
        self.assertEqual(
            [label.label for label in snapshot.buttons], ["Time", "Pause", "End", "-"]
        )

    def test_focus_running_reveals_clock_for_five_seconds(self) -> None:
        session = Session(
            id="s1",
            kind=SessionKind.FOCUS,
            terms=FocusTerms(1500, 300, 60_000, 30, 30, "UTC"),
            status=SessionStatus.RUNNING,
            committed_active_ms=0,
        )
        state = GameState(user_id="u1", pet_id="p1", active_session=session)
        sample = TimerSample(
            session_id="s1", active_ms=1000, remaining_seconds=1499, due=False
        )
        runtime = _runtime(Screen.FOCUS, 3, clock_reveal_until_mono_ms=5_000)

        revealing = build(
            state,
            runtime,
            sample,
            _clock(14, 32, monotonic_ms=1_000),
            CONFIG,
            BINDINGS,
            ACTIONS,
            DEVICE_BUTTONS,
        )
        self.assertEqual(revealing.clock_text, "14:32")
        self.assertIsNone(revealing.timer_seconds)

        expired = build(
            state,
            runtime,
            sample,
            _clock(14, 32, monotonic_ms=5_001),
            CONFIG,
            BINDINGS,
            ACTIONS,
            DEVICE_BUTTONS,
        )
        self.assertIsNone(expired.clock_text)
        self.assertEqual(expired.timer_seconds, 1499)

    def test_focus_paused_matches_fixture(self) -> None:
        session = Session(
            id="s1",
            kind=SessionKind.FOCUS,
            terms=FocusTerms(1500, 300, 60_000, 30, 30, "UTC"),
            status=SessionStatus.PAUSED,
            committed_active_ms=30_000,
        )
        state = GameState(user_id="u1", pet_id="p1", active_session=session)
        sample = TimerSample(
            session_id="s1", active_ms=30_000, remaining_seconds=1470, due=False
        )
        snapshot = build(
            state,
            _runtime(Screen.FOCUS, 4),
            sample,
            _clock(14, 32),
            CONFIG,
            BINDINGS,
            ACTIONS,
            DEVICE_BUTTONS,
        )
        self.assertEqual(snapshot.mood, "idle")
        self.assertEqual(snapshot.timer_seconds, 1470)
        self.assertTrue(snapshot.paused)
        self.assertEqual(
            [label.label for label in snapshot.buttons], ["Time", "Resume", "End", "-"]
        )

    def test_break_offer_matches_fixture(self) -> None:
        state = GameState(
            user_id="u1",
            pet_id="p1",
            last_focus_minutes=25,
            pending_break=BreakOffer(
                parent_focus_id="s1", duration_seconds=300, report_timezone="UTC"
            ),
            latest_reaction=Reaction(
                mood=ReactionMood.HAPPY,
                expires_at=datetime(2026, 9, 13, 14, 33, tzinfo=UTC),
            ),
        )
        snapshot = build(
            state,
            _runtime(Screen.BREAK_OFFER, 5),
            None,
            _clock(14, 32),
            CONFIG,
            BINDINGS,
            ACTIONS,
            DEVICE_BUTTONS,
        )
        self.assertEqual(snapshot.mood, "party")
        self.assertIsNone(snapshot.timer_seconds)
        self.assertEqual(snapshot.break_minutes, 5)
        self.assertEqual(
            [label.label for label in snapshot.buttons], ["Break", "Again", "Home", "-"]
        )

    def test_break_offer_rounds_up_a_debug_sessions_short_break(self) -> None:
        state = GameState(
            user_id="u1",
            pet_id="p1",
            pending_break=BreakOffer(
                parent_focus_id="s1", duration_seconds=10, report_timezone="UTC"
            ),
        )
        snapshot = build(
            state,
            _runtime(Screen.BREAK_OFFER, 5),
            None,
            _clock(14, 32),
            CONFIG,
            BINDINGS,
            ACTIONS,
            DEVICE_BUTTONS,
        )
        self.assertEqual(snapshot.break_minutes, 1)

    def test_break_running_matches_fixture(self) -> None:
        session = Session(
            id="s2",
            kind=SessionKind.BREAK,
            terms=BreakTerms(300, "s1", "UTC"),
            status=SessionStatus.RUNNING,
            committed_active_ms=0,
        )
        state = GameState(
            user_id="u1", pet_id="p1", last_focus_minutes=25, active_session=session
        )
        sample = TimerSample(
            session_id="s2", active_ms=0, remaining_seconds=300, due=False
        )
        snapshot = build(
            state,
            _runtime(Screen.BREAK, 6),
            sample,
            _clock(14, 32),
            CONFIG,
            BINDINGS,
            ACTIONS,
            DEVICE_BUTTONS,
        )
        self.assertEqual(snapshot.mood, "sleeping")
        self.assertEqual(snapshot.timer_seconds, 300)
        self.assertFalse(snapshot.paused)
        self.assertIsNone(snapshot.break_minutes)
        self.assertEqual(
            [label.label for label in snapshot.buttons],
            ["Again", "Home", "-", "-"],
        )

    def test_home_with_sad_reaction_matches_fixture(self) -> None:
        state = GameState(
            user_id="u1",
            pet_id="p1",
            latest_reaction=Reaction(
                mood=ReactionMood.SAD,
                expires_at=datetime(2026, 9, 13, 14, 36, tzinfo=UTC),
            ),
            needs_comfort=True,
        )
        snapshot = build(
            state,
            _runtime(Screen.HOME, 7),
            None,
            _clock(14, 35),
            CONFIG,
            BINDINGS,
            ACTIONS,
            DEVICE_BUTTONS,
        )
        self.assertEqual(snapshot.mood, "sad")
        self.assertEqual(snapshot.clock_text, "14:35")
        self.assertEqual(
            [label.label for label in snapshot.buttons], ["Feed", "Focus", "Pet", "-"]
        )


def _committed(draft: EventDraft) -> DomainEvent:
    return DomainEvent(
        seq=1,
        event=UncommittedEvent(
            event_id=uuid4(),
            occurred_at=datetime(2026, 9, 13, 14, 32, tzinfo=UTC),
            user_id="u1",
            device_id="d1",
            draft=draft,
        ),
    )


class PresenterNavigationTests(unittest.TestCase):
    def test_focus_started_opens_focus_screen(self) -> None:
        draft = FocusSessionStarted(
            source=EventSource.SYSTEM,
            dedupe_key="k1",
            session_id="s1",
            terms=FocusTerms(1500, 300, 60_000, 30, 30, "UTC"),
        )
        runtime = _runtime(Screen.HOME, 1)
        result = on_commit(_committed(draft), runtime, {})
        self.assertEqual(result.screen, Screen.FOCUS)
        self.assertEqual(result.cues, ())

    def test_break_started_opens_break_screen(self) -> None:
        draft = BreakSessionStarted(
            source=EventSource.SYSTEM,
            dedupe_key="k2",
            session_id="s2",
            terms=BreakTerms(300, "s1", "UTC"),
        )
        result = on_commit(_committed(draft), _runtime(Screen.BREAK_OFFER, 5), {})
        self.assertEqual(result.screen, Screen.BREAK)

    def test_focus_completion_opens_break_offer_with_celebrate_cue(self) -> None:
        draft = FocusSessionCompleted(
            source=EventSource.SYSTEM,
            dedupe_key="k3",
            session_id="s1",
            active_ms=1_500_000,
            credit_date=datetime(2026, 9, 13, tzinfo=UTC).date(),
            break_offer=BreakOffer("s1", 300, "UTC"),
            reaction=Reaction(
                ReactionMood.HAPPY, datetime(2026, 9, 13, 14, 33, tzinfo=UTC)
            ),
        )
        result = on_commit(_committed(draft), _runtime(Screen.FOCUS, 3), {})
        self.assertEqual(result.screen, Screen.BREAK_OFFER)
        self.assertEqual(len(result.cues), 1)
        self.assertEqual(result.cues[0].name, "celebrate")

    def test_feed_stays_home_with_feed_cue_and_sprite(self) -> None:
        draft = PetFed(
            source=EventSource.LOCAL_CONTROLS,
            dedupe_key="k4",
            food_id="food_basic",
            reaction=Reaction(
                ReactionMood.CONTENT, datetime(2026, 9, 13, 14, 33, tzinfo=UTC)
            ),
        )
        food_definitions = {
            "food_basic": FoodDefinition(
                id="food_basic", sprite_id="sandwich", content_seconds=60
            )
        }
        result = on_commit(
            _committed(draft), _runtime(Screen.HOME, 1), food_definitions
        )
        self.assertEqual(result.screen, Screen.HOME)
        self.assertEqual(len(result.cues), 1)
        self.assertEqual(result.cues[0].name, "feed")
        self.assertEqual(result.cues[0].food_sprite, "sandwich")

    def test_pet_comforted_stays_home_without_its_own_cue(self) -> None:
        # The pet cue is sent unconditionally on every Pet press by
        # application._pet_once, not tied to this specific event.
        draft = PetComforted(
            source=EventSource.LOCAL_CONTROLS,
            dedupe_key="k5",
            reaction=Reaction(
                ReactionMood.HAPPY, datetime(2026, 9, 13, 14, 33, tzinfo=UTC)
            ),
        )
        result = on_commit(_committed(draft), _runtime(Screen.HOME, 1), {})
        self.assertEqual(result.screen, Screen.HOME)
        self.assertEqual(result.cues, ())

    def test_sound_preference_changed_stays_on_current_screen_without_a_cue(
        self,
    ) -> None:
        draft = SoundPreferenceChanged(
            source=EventSource.LOCAL_CONTROLS,
            dedupe_key="k6",
            sound_enabled=False,
        )
        result = on_commit(_committed(draft), _runtime(Screen.SETTINGS, 1), {})
        self.assertEqual(result.screen, Screen.SETTINGS)
        self.assertEqual(result.cues, ())


if __name__ == "__main__":
    unittest.main()
