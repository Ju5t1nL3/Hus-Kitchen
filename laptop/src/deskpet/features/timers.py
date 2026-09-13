"""Pure focus and break decisions.

This module validates commands and returns event drafts. It does not mutate state,
read clocks/configuration implicitly, persist events, or update the UI.
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import assert_never
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from deskpet.core.commands import (
    Accepted,
    CompleteSession,
    Decision,
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
    BreakSessionCompleted,
    BreakSessionEnded,
    BreakSessionStarted,
    BreakSkipped,
    EndReason,
    EventSource,
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
    Reaction,
    ReactionMood,
    RejectionCode,
    Session,
    SessionKind,
    SessionStatus,
    TimerSample,
)

type TimerCommand = (
    StartFocus
    | StartBreak
    | PauseSession
    | ResumeSession
    | EndSession
    | CompleteSession
    | SkipBreak
)


@dataclass(frozen=True, slots=True)
class BreakPolicy:
    focus_minutes_per_break_minute: int = 5
    minimum_break_minutes: int = 1

    def __post_init__(self) -> None:
        if self.focus_minutes_per_break_minute <= 0:
            raise ValueError("focus_minutes_per_break_minute must be positive")
        if self.minimum_break_minutes <= 0:
            raise ValueError("minimum_break_minutes must be positive")


@dataclass(frozen=True, slots=True)
class TimerRules:
    allowed_focus_minutes: tuple[int, ...]
    break_policy: BreakPolicy
    grace_active_ms: int
    sad_seconds: int
    happy_seconds: int
    report_timezone: str

    def __post_init__(self) -> None:
        if not self.allowed_focus_minutes:
            raise ValueError("allowed_focus_minutes must not be empty")
        if tuple(sorted(set(self.allowed_focus_minutes))) != self.allowed_focus_minutes:
            raise ValueError("allowed_focus_minutes must be sorted and unique")
        if any(
            minutes < 5 or minutes > 60 or minutes % 5 != 0
            for minutes in self.allowed_focus_minutes
        ):
            raise ValueError(
                "allowed focus minutes must be multiples of 5 from 5 to 60"
            )
        if self.grace_active_ms < 0:
            raise ValueError("grace_active_ms must be nonnegative")
        if self.sad_seconds <= 0 or self.happy_seconds <= 0:
            raise ValueError("reaction durations must be positive")
        try:
            ZoneInfo(self.report_timezone)
        except ZoneInfoNotFoundError as error:
            raise ValueError("report_timezone must be a known IANA timezone") from error


# A dev-only debug duration reachable by cycling Down past the shortest
# configured focus length. `0` is not itself a real minute count (allowed
# durations are always 5-60); it is the sentinel Setup/StartFocus use for a
# fixed DEBUG_FOCUS_SECONDS-long session, so it does not need a config entry
# of its own and never appears in `allowed_focus_minutes`.
DEBUG_FOCUS_MINUTES = 0
DEBUG_FOCUS_SECONDS = 10


def next_focus_minutes(current: int, allowed: tuple[int, ...]) -> int:
    """Return the next configured duration, wrapping after the final value."""
    if not allowed:
        raise ValueError("allowed durations must not be empty")
    if current == DEBUG_FOCUS_MINUTES:
        return allowed[0]
    try:
        index = allowed.index(current)
    except ValueError as error:
        raise ValueError("current duration is not allowed") from error
    return allowed[(index + 1) % len(allowed)]


def previous_focus_minutes(current: int, allowed: tuple[int, ...]) -> int:
    """Return the preceding configured duration, wrapping before the first value.

    Stepping down from the shortest configured duration lands on
    `DEBUG_FOCUS_MINUTES` (a fixed-length debug session) before continuing to
    wrap to the longest duration on the next press.
    """
    if not allowed:
        raise ValueError("allowed durations must not be empty")
    if current == DEBUG_FOCUS_MINUTES:
        return allowed[-1]
    try:
        index = allowed.index(current)
    except ValueError as error:
        raise ValueError("current duration is not allowed") from error
    if index == 0:
        return DEBUG_FOCUS_MINUTES
    return allowed[index - 1]


def break_minutes(focus_minutes: int, policy: BreakPolicy) -> int:
    """Calculate a proportional break using round-half-up integer arithmetic."""
    if focus_minutes <= 0:
        raise ValueError("focus_minutes must be positive")
    divisor = policy.focus_minutes_per_break_minute
    rounded = (2 * focus_minutes + divisor) // (2 * divisor)
    return max(policy.minimum_break_minutes, rounded)


def decide(
    state: GameState,
    command: TimerCommand,
    sample: TimerSample | None,
    rules: TimerRules,
    now: ClockReading,
) -> Decision:
    """Validate one timer request and return at most one event draft."""
    match command:
        case StartFocus():
            return _start_focus(state, command, sample, rules)
        case StartBreak():
            return _start_break(state, command, sample)
        case PauseSession():
            return _pause(state, command, sample)
        case ResumeSession():
            return _resume(state, command, sample)
        case EndSession():
            return _end(state, command, sample, now)
        case CompleteSession():
            return _complete(state, command, sample, now)
        case SkipBreak():
            return _skip_break(state, command, sample)
        case _ as unreachable:
            assert_never(unreachable)


def _start_focus(
    state: GameState,
    command: StartFocus,
    sample: TimerSample | None,
    rules: TimerRules,
) -> Decision:
    _require_no_sample(sample)
    if state.active_session is not None or state.pending_break is not None:
        return Rejected(RejectionCode.UNAVAILABLE)
    if command.minutes == DEBUG_FOCUS_MINUTES:
        return Accepted(
            FocusSessionStarted(
                source=EventSource.SYSTEM,
                dedupe_key=f"session-start:{command.session_id}",
                session_id=command.session_id,
                terms=FocusTerms(
                    duration_seconds=DEBUG_FOCUS_SECONDS,
                    break_seconds=DEBUG_FOCUS_SECONDS,
                    grace_active_ms=rules.grace_active_ms,
                    sad_seconds=rules.sad_seconds,
                    happy_seconds=rules.happy_seconds,
                    report_timezone=rules.report_timezone,
                    is_debug=True,
                ),
            )
        )
    if command.minutes not in rules.allowed_focus_minutes:
        return Rejected(RejectionCode.INVALID_DURATION)
    proposed_break = break_minutes(command.minutes, rules.break_policy)
    return Accepted(
        FocusSessionStarted(
            source=EventSource.SYSTEM,
            dedupe_key=f"session-start:{command.session_id}",
            session_id=command.session_id,
            terms=FocusTerms(
                duration_seconds=command.minutes * 60,
                break_seconds=proposed_break * 60,
                grace_active_ms=rules.grace_active_ms,
                sad_seconds=rules.sad_seconds,
                happy_seconds=rules.happy_seconds,
                report_timezone=rules.report_timezone,
            ),
        )
    )


def _start_break(
    state: GameState,
    command: StartBreak,
    sample: TimerSample | None,
) -> Decision:
    _require_no_sample(sample)
    if state.active_session is not None:
        return Rejected(RejectionCode.UNAVAILABLE)
    offer = state.pending_break
    if offer is None or offer.parent_focus_id != command.parent_focus_id:
        return Rejected(RejectionCode.NO_BREAK_OFFER)
    return Accepted(
        BreakSessionStarted(
            source=EventSource.SYSTEM,
            dedupe_key=f"break-choice:{offer.parent_focus_id}",
            session_id=command.session_id,
            terms=BreakTerms(
                duration_seconds=offer.duration_seconds,
                parent_focus_id=offer.parent_focus_id,
                report_timezone=offer.report_timezone,
            ),
        )
    )


def _pause(
    state: GameState,
    command: PauseSession,
    sample: TimerSample | None,
) -> Decision:
    session = _matching_session(state, command.session_id)
    if session is None:
        return Rejected(RejectionCode.NO_SESSION)
    if session.kind is SessionKind.BREAK:
        return Rejected(RejectionCode.UNAVAILABLE)
    if session.status is not SessionStatus.RUNNING:
        return Rejected(RejectionCode.WRONG_SESSION_STATE)
    checked = _require_sample(session, sample)
    if checked.due:
        return NoOp()
    return Accepted(
        FocusSessionPaused(
            source=EventSource.SYSTEM,
            dedupe_key=command.operation_key,
            session_id=session.id,
            active_ms=checked.active_ms,
        )
    )


def _resume(
    state: GameState,
    command: ResumeSession,
    sample: TimerSample | None,
) -> Decision:
    session = _matching_session(state, command.session_id)
    if session is None:
        return Rejected(RejectionCode.NO_SESSION)
    if session.kind is SessionKind.BREAK:
        return Rejected(RejectionCode.UNAVAILABLE)
    if session.status is not SessionStatus.PAUSED:
        return Rejected(RejectionCode.WRONG_SESSION_STATE)
    checked = _require_sample(session, sample)
    if checked.active_ms != session.committed_active_ms or checked.due:
        raise ValueError("paused resume sample does not match saved active time")
    return Accepted(
        FocusSessionResumed(
            source=EventSource.SYSTEM,
            dedupe_key=command.operation_key,
            session_id=session.id,
            active_ms=checked.active_ms,
        )
    )


def _end(
    state: GameState,
    command: EndSession,
    sample: TimerSample | None,
    now: ClockReading,
) -> Decision:
    session = _matching_session(state, command.session_id)
    if session is None:
        return Rejected(RejectionCode.NO_SESSION)
    checked = _require_sample(session, sample)
    if checked.due:
        return NoOp()

    if session.kind is SessionKind.BREAK:
        reason = _break_end_reason(command.reason)
        return Accepted(
            BreakSessionEnded(
                source=EventSource.SYSTEM,
                dedupe_key=f"session-terminal:{session.id}",
                session_id=session.id,
                active_ms=checked.active_ms,
                reason=reason,
            )
        )

    terms = _focus_terms(session)
    reason = _focus_end_reason(command.reason, checked.active_ms, terms)
    reaction = None
    if reason is EndReason.USER_EARLY:
        reaction = Reaction(
            mood=ReactionMood.SAD,
            expires_at=now.utc + timedelta(seconds=terms.sad_seconds),
        )
    return Accepted(
        FocusSessionEnded(
            source=EventSource.SYSTEM,
            dedupe_key=f"session-terminal:{session.id}",
            session_id=session.id,
            active_ms=checked.active_ms,
            reason=reason,
            reaction=reaction,
        )
    )


def _complete(
    state: GameState,
    command: CompleteSession,
    sample: TimerSample | None,
    now: ClockReading,
) -> Decision:
    session = _matching_session(state, command.session_id)
    if session is None:
        return Rejected(RejectionCode.NO_SESSION)
    if session.status is not SessionStatus.RUNNING:
        return Rejected(RejectionCode.WRONG_SESSION_STATE)
    checked = _require_sample(session, sample)
    if not checked.due:
        return Rejected(RejectionCode.WRONG_SESSION_STATE)

    if session.kind is SessionKind.BREAK:
        return Accepted(
            BreakSessionCompleted(
                source=EventSource.SYSTEM,
                dedupe_key=f"session-terminal:{session.id}",
                session_id=session.id,
                active_ms=checked.active_ms,
            )
        )

    terms = _focus_terms(session)
    return Accepted(
        FocusSessionCompleted(
            source=EventSource.SYSTEM,
            dedupe_key=f"session-terminal:{session.id}",
            session_id=session.id,
            active_ms=checked.active_ms,
            credit_date=now.utc.astimezone(ZoneInfo(terms.report_timezone)).date(),
            break_offer=BreakOffer(
                parent_focus_id=session.id,
                duration_seconds=terms.break_seconds,
                report_timezone=terms.report_timezone,
            ),
            reaction=Reaction(
                mood=ReactionMood.HAPPY,
                expires_at=now.utc + timedelta(seconds=terms.happy_seconds),
            ),
        )
    )


def _skip_break(
    state: GameState,
    command: SkipBreak,
    sample: TimerSample | None,
) -> Decision:
    _require_no_sample(sample)
    if state.active_session is not None:
        return Rejected(RejectionCode.UNAVAILABLE)
    offer = state.pending_break
    if offer is None or offer.parent_focus_id != command.parent_focus_id:
        return Rejected(RejectionCode.NO_BREAK_OFFER)
    return Accepted(
        BreakSkipped(
            source=EventSource.SYSTEM,
            dedupe_key=f"break-choice:{offer.parent_focus_id}",
            parent_focus_id=offer.parent_focus_id,
        )
    )


def _matching_session(state: GameState, session_id: str) -> Session | None:
    session = state.active_session
    if session is None or session.id != session_id:
        return None
    return session


def _require_sample(session: Session, sample: TimerSample | None) -> TimerSample:
    if sample is None:
        raise ValueError("this command requires a timer sample")
    if sample.session_id != session.id:
        raise ValueError("timer sample belongs to another session")
    duration_ms = session.terms.duration_seconds * 1_000
    if sample.active_ms < session.committed_active_ms or sample.active_ms > duration_ms:
        raise ValueError("timer sample active time is outside session bounds")
    expected_due = sample.active_ms == duration_ms
    expected_remaining = (duration_ms - sample.active_ms + 999) // 1_000
    if sample.due is not expected_due or sample.remaining_seconds != expected_remaining:
        raise ValueError("timer sample fields are inconsistent")
    if session.status is SessionStatus.PAUSED and (
        sample.active_ms != session.committed_active_ms
    ):
        raise ValueError("paused sample must equal saved active time")
    return sample


def _require_no_sample(sample: TimerSample | None) -> None:
    if sample is not None:
        raise ValueError("this command does not accept a timer sample")


def _focus_terms(session: Session) -> FocusTerms:
    if not isinstance(session.terms, FocusTerms):
        raise TypeError("focus session has non-focus terms")
    return session.terms


def _focus_end_reason(
    requested: RequestedEndReason,
    active_ms: int,
    terms: FocusTerms,
) -> EndReason:
    if requested is RequestedEndReason.USER:
        if active_ms < terms.grace_active_ms:
            return EndReason.USER_GRACE
        return EndReason.USER_EARLY
    return EndReason(requested.value)


def _break_end_reason(requested: RequestedEndReason) -> EndReason:
    if requested is RequestedEndReason.USER:
        return EndReason.USER_BREAK
    return EndReason(requested.value)
