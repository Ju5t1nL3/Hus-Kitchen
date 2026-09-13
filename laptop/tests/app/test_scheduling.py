"""Tests for pure timer sampling and wake scheduling."""

import unittest
from datetime import UTC, datetime, timedelta

from deskpet.app.scheduling import advance, sample
from deskpet.core.models import (
    ClockReading,
    FocusTerms,
    GameState,
    Reaction,
    ReactionMood,
    RuntimeState,
    Screen,
    Session,
    SessionKind,
    SessionStatus,
)
from deskpet.core.views import InterruptedSchedule, NormalSchedule

NOW = ClockReading(datetime(2026, 9, 13, tzinfo=UTC), 10_000, False)


def focus(status: SessionStatus = SessionStatus.RUNNING) -> Session:
    return Session(
        "focus-1",
        SessionKind.FOCUS,
        FocusTerms(300, 60, 60_000, 30, 30, "UTC"),
        status,
        12_000,
    )


def runtime(*, anchor: int | None = 8_000, reveal: int | None = None) -> RuntimeState:
    return RuntimeState(Screen.FOCUS, 25, anchor, NOW, 1, None, None, reveal)


class TimerSamplingTests(unittest.TestCase):
    def test_running_and_paused_samples_use_only_active_time(self) -> None:
        running = sample(focus(), 8_000, 10_000)
        paused = sample(focus(SessionStatus.PAUSED), None, 99_000)

        self.assertEqual(running.active_ms, 14_000)
        self.assertEqual(running.remaining_seconds, 286)
        self.assertEqual(paused.active_ms, 12_000)
        self.assertEqual(paused.remaining_seconds, 288)

    def test_sample_clamps_at_the_session_deadline(self) -> None:
        result = sample(focus(), 8_000, 400_000)

        self.assertTrue(result.due)
        self.assertEqual(result.active_ms, 300_000)
        self.assertEqual(result.remaining_seconds, 0)


class WakeSchedulingTests(unittest.TestCase):
    def test_clock_reveal_and_reaction_expiry_can_wake_before_next_second(self) -> None:
        state = GameState(
            "user-1",
            "pet-1",
            active_session=focus(),
            latest_reaction=Reaction(
                ReactionMood.HAPPY, NOW.utc + timedelta(milliseconds=300)
            ),
        )

        result = advance(state, runtime(reveal=NOW.monotonic_ms + 500), NOW)

        self.assertIsInstance(result, NormalSchedule)
        assert isinstance(result, NormalSchedule)
        self.assertEqual(result.next_wake_mono_ms, NOW.monotonic_ms + 300)

    def test_resume_signal_returns_an_interruption_for_application_policy(self) -> None:
        resumed = ClockReading(NOW.utc, NOW.monotonic_ms, True)

        result = advance(
            GameState("user-1", "pet-1", active_session=focus()), runtime(), resumed
        )

        self.assertEqual(result, InterruptedSchedule("focus-1"))

    def test_expired_reaction_does_not_create_a_zero_delay_busy_loop(self) -> None:
        state = GameState(
            "user-1",
            "pet-1",
            latest_reaction=Reaction(
                ReactionMood.HAPPY, NOW.utc - timedelta(milliseconds=1)
            ),
        )

        result = advance(state, runtime(), NOW)

        self.assertIsInstance(result, NormalSchedule)
        assert isinstance(result, NormalSchedule)
        self.assertEqual(result.next_wake_mono_ms, NOW.monotonic_ms + 1_000)


if __name__ == "__main__":
    unittest.main()
