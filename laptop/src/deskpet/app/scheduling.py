"""Pure timer sampling and application wake scheduling."""

from datetime import datetime

from deskpet.core.models import (
    ClockReading,
    GameState,
    RuntimeState,
    Session,
    SessionStatus,
    TimerSample,
)
from deskpet.core.views import InterruptedSchedule, NormalSchedule, ScheduleResult

_REFRESH_MS = 1_000


def sample(
    session: Session,
    run_anchor_mono_ms: int | None,
    now_mono_ms: int,
) -> TimerSample:
    """Derive trusted cumulative progress without mutating the session."""
    if now_mono_ms < 0:
        raise ValueError("now_mono_ms must be nonnegative")
    if session.status is SessionStatus.PAUSED or run_anchor_mono_ms is None:
        active_ms = session.committed_active_ms
    else:
        if now_mono_ms < run_anchor_mono_ms:
            raise ValueError("monotonic clock moved behind the run anchor")
        active_ms = session.committed_active_ms + now_mono_ms - run_anchor_mono_ms
    duration_ms = session.terms.duration_seconds * 1_000
    active_ms = min(active_ms, duration_ms)
    return TimerSample(
        session_id=session.id,
        active_ms=active_ms,
        remaining_seconds=(duration_ms - active_ms + 999) // 1_000,
        due=active_ms == duration_ms,
    )


def advance(
    state: GameState,
    runtime: RuntimeState,
    now: ClockReading,
) -> ScheduleResult:
    """Return the current sample and earliest ordinary presentation wake."""
    session = state.active_session
    if now.resumed:
        return InterruptedSchedule(session.id if session is not None else None)

    current = (
        sample(session, runtime.run_anchor_mono_ms, now.monotonic_ms)
        if session is not None
        else None
    )
    next_wake = now.monotonic_ms + _REFRESH_MS

    if current is not None and not current.due:
        until_next_second = current.active_ms % _REFRESH_MS
        until_next_second = _REFRESH_MS - until_next_second
        next_wake = min(next_wake, now.monotonic_ms + until_next_second)
    if runtime.clock_reveal_until_mono_ms is not None:
        next_wake = min(next_wake, runtime.clock_reveal_until_mono_ms)
    reaction = state.latest_reaction
    if reaction is not None:
        expiry_ms = _utc_deadline_to_mono_ms(reaction.expires_at, now)
        next_wake = min(next_wake, expiry_ms)

    return NormalSchedule(
        sample=current, next_wake_mono_ms=max(now.monotonic_ms, next_wake)
    )


def _utc_deadline_to_mono_ms(deadline: datetime, now: ClockReading) -> int:
    remaining_ms = max(0, int((deadline - now.utc).total_seconds() * 1_000))
    return now.monotonic_ms + remaining_ms
