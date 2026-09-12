"""Tests for pure focus and break decisions."""

import unittest
from datetime import UTC, datetime

from deskpet.core.commands import (
    Accepted,
    CompleteSession,
    EndSession,
    NoOp,
    PauseSession,
    Rejected,
    RequestedEndReason,
    ResumeSession,
    SkipBreak,
    StartBreak,
    StartFocus,
)
from deskpet.core.events import (
    BreakSessionEnded,
    BreakSessionStarted,
    BreakSkipped,
    EndReason,
    FocusSessionCompleted,
    FocusSessionEnded,
    FocusSessionPaused,
    FocusSessionResumed,
    FocusSessionStarted,
)
from deskpet.core.models import (
    BreakOffer,
    BreakTerms,
    ClockReading,
    FocusTerms,
    GameState,
    ReactionMood,
    RejectionCode,
    Session,
    SessionKind,
    SessionStatus,
    TimerSample,
)
from deskpet.features.timers import (
    BreakPolicy,
    TimerRules,
    break_minutes,
    decide,
    next_focus_minutes,
)

NOW = ClockReading(datetime(2026, 9, 13, 4, 30, tzinfo=UTC), 100_000, False)
ALLOWED_MINUTES = tuple(range(5, 61, 5))
RULES = TimerRules(
    allowed_focus_minutes=ALLOWED_MINUTES,
    break_policy=BreakPolicy(),
    grace_active_ms=60_000,
    sad_seconds=30,
    happy_seconds=30,
    report_timezone="America/Chicago",
)


def empty_state(*, pending_break: BreakOffer | None = None) -> GameState:
    return GameState("user-1", "pet-1", pending_break=pending_break)


def focus_session(
    *,
    status: SessionStatus = SessionStatus.RUNNING,
    committed_active_ms: int = 0,
) -> Session:
    return Session(
        id="focus-1",
        kind=SessionKind.FOCUS,
        terms=FocusTerms(
            duration_seconds=300,
            break_seconds=60,
            grace_active_ms=60_000,
            sad_seconds=30,
            happy_seconds=30,
            report_timezone="America/Chicago",
        ),
        status=status,
        committed_active_ms=committed_active_ms,
    )


def break_session(
    *,
    status: SessionStatus = SessionStatus.RUNNING,
    committed_active_ms: int = 0,
) -> Session:
    return Session(
        id="break-1",
        kind=SessionKind.BREAK,
        terms=BreakTerms(60, "focus-1", "America/Chicago"),
        status=status,
        committed_active_ms=committed_active_ms,
    )


def state_with(session: Session) -> GameState:
    return GameState("user-1", "pet-1", active_session=session)


def sample(session_id: str, active_ms: int, duration_ms: int = 300_000) -> TimerSample:
    return TimerSample(
        session_id=session_id,
        active_ms=active_ms,
        remaining_seconds=(duration_ms - active_ms + 999) // 1_000,
        due=active_ms == duration_ms,
    )


class DurationRuleTests(unittest.TestCase):
    def test_duration_wraps_from_60_to_5(self) -> None:
        self.assertEqual(next_focus_minutes(5, ALLOWED_MINUTES), 10)
        self.assertEqual(next_focus_minutes(60, ALLOWED_MINUTES), 5)

    def test_proportional_break_examples(self) -> None:
        policy = BreakPolicy()
        self.assertEqual(break_minutes(5, policy), 1)
        self.assertEqual(break_minutes(25, policy), 5)
        self.assertEqual(break_minutes(60, policy), 12)

    def test_rules_reject_duration_the_display_protocol_cannot_represent(self) -> None:
        with self.assertRaisesRegex(ValueError, "multiples of 5"):
            TimerRules(
                allowed_focus_minutes=(7,),
                break_policy=BreakPolicy(),
                grace_active_ms=60_000,
                sad_seconds=30,
                happy_seconds=30,
                report_timezone="America/Chicago",
            )


class StartRuleTests(unittest.TestCase):
    def test_start_focus_pins_current_rules_in_event(self) -> None:
        state = empty_state()

        result = decide(state, StartFocus("focus-1", 25), None, RULES, NOW)

        self.assertIsInstance(result, Accepted)
        assert isinstance(result, Accepted)
        self.assertIsInstance(result.event, FocusSessionStarted)
        assert isinstance(result.event, FocusSessionStarted)
        self.assertEqual(result.event.terms.duration_seconds, 1_500)
        self.assertEqual(result.event.terms.break_seconds, 300)
        self.assertEqual(state, empty_state(), "decide must not mutate its input")

    def test_start_focus_rejects_unconfigured_duration(self) -> None:
        result = decide(empty_state(), StartFocus("focus-1", 7), None, RULES, NOW)

        self.assertEqual(result, Rejected(RejectionCode.INVALID_DURATION))

    def test_start_and_skip_break_require_matching_offer(self) -> None:
        offer = BreakOffer("focus-1", 300, "America/Chicago")
        state = empty_state(pending_break=offer)

        started = decide(state, StartBreak("break-1", "focus-1"), None, RULES, NOW)
        skipped = decide(state, SkipBreak("focus-1"), None, RULES, NOW)

        self.assertIsInstance(started, Accepted)
        assert isinstance(started, Accepted)
        self.assertIsInstance(started.event, BreakSessionStarted)
        self.assertIsInstance(skipped, Accepted)
        assert isinstance(skipped, Accepted)
        self.assertIsInstance(skipped.event, BreakSkipped)
        self.assertEqual(
            started.event.dedupe_key,
            skipped.event.dedupe_key,
            "start and skip must conflict as one break choice",
        )


class PauseResumeRuleTests(unittest.TestCase):
    def test_pause_and_resume_emit_cumulative_active_time(self) -> None:
        running = state_with(focus_session())
        paused = state_with(
            focus_session(status=SessionStatus.PAUSED, committed_active_ms=45_000)
        )

        pause_result = decide(
            running,
            PauseSession("focus-1", "button:link:1"),
            sample("focus-1", 45_000),
            RULES,
            NOW,
        )
        resume_result = decide(
            paused,
            ResumeSession("focus-1", "button:link:2"),
            sample("focus-1", 45_000),
            RULES,
            NOW,
        )

        self.assertIsInstance(pause_result, Accepted)
        assert isinstance(pause_result, Accepted)
        assert isinstance(pause_result.event, FocusSessionPaused)
        self.assertEqual(pause_result.event.dedupe_key, "button:link:1")
        self.assertEqual(pause_result.event.active_ms, 45_000)
        self.assertIsInstance(resume_result, Accepted)
        assert isinstance(resume_result, Accepted)
        self.assertIsInstance(resume_result.event, FocusSessionResumed)
        assert isinstance(resume_result.event, FocusSessionResumed)
        self.assertEqual(resume_result.event.active_ms, 45_000)

    def test_break_sessions_cannot_be_paused_or_resumed(self) -> None:
        running = state_with(break_session())
        paused = state_with(
            break_session(status=SessionStatus.PAUSED, committed_active_ms=10_000)
        )

        pause_result = decide(
            running,
            PauseSession("break-1", "button:link:1"),
            sample("break-1", 10_000, duration_ms=60_000),
            RULES,
            NOW,
        )
        resume_result = decide(
            paused,
            ResumeSession("break-1", "button:link:2"),
            sample("break-1", 10_000, duration_ms=60_000),
            RULES,
            NOW,
        )

        self.assertEqual(pause_result, Rejected(RejectionCode.UNAVAILABLE))
        self.assertEqual(resume_result, Rejected(RejectionCode.UNAVAILABLE))

    def test_paused_time_cannot_appear_in_resume_sample(self) -> None:
        paused = state_with(
            focus_session(status=SessionStatus.PAUSED, committed_active_ms=45_000)
        )

        with self.assertRaisesRegex(ValueError, "paused sample"):
            decide(
                paused,
                ResumeSession("focus-1", "button:link:2"),
                sample("focus-1", 46_000),
                RULES,
                NOW,
            )


class EndAndCompletionRuleTests(unittest.TestCase):
    def test_focus_early_end_boundary(self) -> None:
        state = state_with(focus_session())

        grace = decide(
            state,
            EndSession("focus-1", RequestedEndReason.USER),
            sample("focus-1", 59_999),
            RULES,
            NOW,
        )
        early = decide(
            state,
            EndSession("focus-1", RequestedEndReason.USER),
            sample("focus-1", 60_000),
            RULES,
            NOW,
        )

        assert isinstance(grace, Accepted)
        assert isinstance(grace.event, FocusSessionEnded)
        self.assertIs(grace.event.reason, EndReason.USER_GRACE)
        self.assertIsNone(grace.event.reaction)
        assert isinstance(early, Accepted)
        assert isinstance(early.event, FocusSessionEnded)
        self.assertIs(early.event.reason, EndReason.USER_EARLY)
        self.assertIsNotNone(early.event.reaction)
        assert early.event.reaction is not None
        self.assertIs(early.event.reaction.mood, ReactionMood.SAD)

    def test_end_while_paused_uses_saved_active_time(self) -> None:
        state = state_with(
            focus_session(status=SessionStatus.PAUSED, committed_active_ms=59_999)
        )

        result = decide(
            state,
            EndSession("focus-1", RequestedEndReason.USER),
            sample("focus-1", 59_999),
            RULES,
            NOW,
        )

        assert isinstance(result, Accepted)
        assert isinstance(result.event, FocusSessionEnded)
        self.assertEqual(result.event.active_ms, 59_999)
        self.assertIs(result.event.reason, EndReason.USER_GRACE)

    def test_user_ending_break_is_neutral(self) -> None:
        state = state_with(break_session())

        result = decide(
            state,
            EndSession("break-1", RequestedEndReason.USER),
            sample("break-1", 30_000, duration_ms=60_000),
            RULES,
            NOW,
        )

        assert isinstance(result, Accepted)
        assert isinstance(result.event, BreakSessionEnded)
        self.assertIs(result.event.reason, EndReason.USER_BREAK)

    def test_system_interruption_is_neutral_after_grace_threshold(self) -> None:
        state = state_with(focus_session())

        result = decide(
            state,
            EndSession("focus-1", RequestedEndReason.APP_SHUTDOWN),
            sample("focus-1", 60_000),
            RULES,
            NOW,
        )

        assert isinstance(result, Accepted)
        assert isinstance(result.event, FocusSessionEnded)
        self.assertIs(result.event.reason, EndReason.APP_SHUTDOWN)
        self.assertIsNone(result.event.reaction)

    def test_due_end_is_noop_so_scheduler_completion_wins(self) -> None:
        state = state_with(focus_session())

        result = decide(
            state,
            EndSession("focus-1", RequestedEndReason.USER),
            sample("focus-1", 300_000),
            RULES,
            NOW,
        )

        self.assertIsInstance(result, NoOp)

    def test_focus_completion_creates_reaction_offer_and_local_credit_date(
        self,
    ) -> None:
        state = state_with(focus_session())

        result = decide(
            state,
            CompleteSession("focus-1"),
            sample("focus-1", 300_000),
            RULES,
            NOW,
        )

        assert isinstance(result, Accepted)
        assert isinstance(result.event, FocusSessionCompleted)
        self.assertEqual(result.event.credit_date.isoformat(), "2026-09-12")
        self.assertEqual(result.event.break_offer.duration_seconds, 60)
        self.assertIs(result.event.reaction.mood, ReactionMood.HAPPY)


if __name__ == "__main__":
    unittest.main()
