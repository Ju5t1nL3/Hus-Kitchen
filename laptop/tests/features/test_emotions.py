"""Tests for event-driven visible emotion selection."""

import unittest
from datetime import UTC, datetime, timedelta

from deskpet.core.models import (
    BreakTerms,
    FocusTerms,
    GameState,
    Mood,
    Reaction,
    ReactionMood,
    Session,
    SessionKind,
    SessionStatus,
)
from deskpet.features.emotions import select

NOW = datetime(2026, 9, 13, 4, 30, tzinfo=UTC)


def session(kind: SessionKind, status: SessionStatus) -> Session:
    terms = (
        FocusTerms(300, 60, 60_000, 30, 30, "America/Chicago")
        if kind is SessionKind.FOCUS
        else BreakTerms(60, "focus-1", "America/Chicago")
    )
    return Session("session-1", kind, terms, status, 0)


def state(
    *,
    active_session: Session | None = None,
    reaction: Reaction | None = None,
) -> GameState:
    return GameState(
        "user-1",
        "pet-1",
        active_session=active_session,
        latest_reaction=reaction,
    )


class EmotionSelectionTests(unittest.TestCase):
    def test_unexpired_latest_reaction_wins_over_activity(self) -> None:
        reaction = Reaction(ReactionMood.CONTENT, NOW + timedelta(seconds=1))
        current = state(
            active_session=session(SessionKind.FOCUS, SessionStatus.RUNNING),
            reaction=reaction,
        )

        self.assertIs(select(current, NOW), Mood.CONTENT)

    def test_reaction_expires_at_exact_deadline_without_reviving_history(self) -> None:
        reaction = Reaction(ReactionMood.SAD, NOW)

        self.assertIs(select(state(reaction=reaction), NOW), Mood.CALM)

    def test_running_sessions_supply_activity_defaults(self) -> None:
        focus = state(active_session=session(SessionKind.FOCUS, SessionStatus.RUNNING))
        resting = state(
            active_session=session(SessionKind.BREAK, SessionStatus.RUNNING)
        )

        self.assertIs(select(focus, NOW), Mood.FOCUSED)
        self.assertIs(select(resting, NOW), Mood.RESTING)

    def test_paused_session_defaults_to_calm(self) -> None:
        paused = state(active_session=session(SessionKind.FOCUS, SessionStatus.PAUSED))

        self.assertIs(select(paused, NOW), Mood.CALM)

    def test_all_reaction_moods_project_to_visible_moods(self) -> None:
        for reaction_mood, expected in (
            (ReactionMood.CONTENT, Mood.CONTENT),
            (ReactionMood.HAPPY, Mood.HAPPY),
            (ReactionMood.SAD, Mood.SAD),
        ):
            with self.subTest(mood=reaction_mood):
                current = state(
                    reaction=Reaction(reaction_mood, NOW + timedelta(seconds=1))
                )
                self.assertIs(select(current, NOW), expected)

    def test_naive_time_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            select(state(), datetime(2026, 9, 13))


if __name__ == "__main__":
    unittest.main()
