"""Tests for the complete M26 mood precedence."""

import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from deskpet.core.models import (
    BreakTerms,
    FocusTerms,
    GameState,
    Mood,
    Reaction,
    ReactionMood,
    RuntimeState,
    Screen,
    Session,
    SessionKind,
    SessionStatus,
)
from deskpet.features.emotions import is_hungry, select

NOW = datetime(2026, 9, 13, 4, 30, tzinfo=UTC)


def runtime(screen: Screen = Screen.HOME) -> RuntimeState:
    return RuntimeState(screen, 25, None, None, 1, None, None)


def focus(status: SessionStatus = SessionStatus.RUNNING) -> Session:
    return Session(
        "focus-1",
        SessionKind.FOCUS,
        FocusTerms(300, 60, 60_000, 30, 30, "America/Chicago"),
        status,
        0,
    )


def break_session() -> Session:
    return Session(
        "break-1",
        SessionKind.BREAK,
        BreakTerms(60, "focus-1", "America/Chicago"),
        SessionStatus.RUNNING,
        0,
    )


class EmotionSelectionTests(unittest.TestCase):
    def test_idle_is_default_and_happy_expires_at_deadline(self) -> None:
        state = GameState("u", "p", last_fed_at=NOW)
        self.assertIs(select(state, NOW, runtime()), Mood.IDLE)
        happy = replace(
            state,
            latest_reaction=Reaction(ReactionMood.HAPPY, NOW + timedelta(seconds=15)),
        )
        self.assertIs(select(happy, NOW, runtime()), Mood.HAPPY)
        self.assertIs(select(happy, NOW + timedelta(seconds=15), runtime()), Mood.IDLE)

    def test_hunger_starts_once_at_five_minutes_and_waits_for_feed(self) -> None:
        state = GameState("u", "p", last_fed_at=NOW)
        self.assertFalse(is_hungry(state, NOW + timedelta(seconds=299), 300))
        self.assertTrue(is_hungry(state, NOW + timedelta(seconds=300), 300))
        self.assertTrue(is_hungry(state, NOW + timedelta(hours=2), 300))

    def test_sad_precedes_hungry_until_comforted(self) -> None:
        state = GameState(
            "u", "p", last_fed_at=NOW - timedelta(minutes=10), needs_comfort=True
        )
        self.assertIs(select(state, NOW, runtime()), Mood.SAD)
        self.assertIs(
            select(replace(state, needs_comfort=False), NOW, runtime()), Mood.HUNGRY
        )

    def test_focus_party_and_pause_screen_states_override_home_moods(self) -> None:
        sad_hungry = GameState(
            "u",
            "p",
            active_session=focus(),
            last_fed_at=NOW - timedelta(minutes=10),
            needs_comfort=True,
        )
        working = runtime(Screen.FOCUS)
        self.assertIs(select(sad_hungry, NOW, working), Mood.WORKING_NEUTRAL)
        self.assertIs(
            select(sad_hungry, NOW, replace(working, attention_lost=True)),
            Mood.WORKING_SAD,
        )
        self.assertIs(
            select(
                replace(sad_hungry, active_session=focus(SessionStatus.PAUSED)),
                NOW,
                working,
            ),
            Mood.IDLE,
        )
        self.assertIs(
            select(
                replace(sad_hungry, active_session=None),
                NOW,
                runtime(Screen.BREAK_OFFER),
            ),
            Mood.PARTY,
        )
        self.assertIs(
            select(
                replace(sad_hungry, active_session=break_session()),
                NOW,
                runtime(Screen.BREAK),
            ),
            Mood.SLEEPING,
        )

    def test_naive_time_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            select(GameState("u", "p"), datetime(2026, 9, 13))


if __name__ == "__main__":
    unittest.main()
