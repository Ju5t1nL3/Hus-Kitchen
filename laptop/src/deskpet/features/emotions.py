"""Pure mood selection and hunger timing."""

from datetime import datetime, timedelta

from deskpet.core.models import (
    GameState,
    Mood,
    RuntimeState,
    Screen,
    SessionKind,
    SessionStatus,
)


def is_hungry(state: GameState, now_utc: datetime, hunger_seconds: int) -> bool:
    """Return whether the one-shot hunger deadline is due."""
    _require_aware(now_utc)
    if hunger_seconds <= 0:
        raise ValueError("hunger_seconds must be positive")
    return state.last_fed_at is not None and now_utc >= state.last_fed_at + timedelta(
        seconds=hunger_seconds
    )


def select(
    state: GameState,
    now_utc: datetime,
    runtime: RuntimeState | None = None,
    hunger_seconds: int = 300,
) -> Mood:
    """Choose the single visible mood using the documented precedence."""
    _require_aware(now_utc)
    if runtime is not None and runtime.screen is Screen.BREAK_OFFER:
        return Mood.PARTY
    if state.active_session is not None and runtime is not None:
        if (
            runtime.screen is Screen.FOCUS
            and state.active_session.status is SessionStatus.RUNNING
        ):
            return Mood.WORKING_SAD if runtime.attention_lost else Mood.WORKING_NEUTRAL
        if state.active_session.kind is SessionKind.BREAK:
            return Mood.SLEEPING
        return Mood.IDLE
    if state.needs_comfort:
        return Mood.SAD
    if is_hungry(state, now_utc, hunger_seconds):
        return Mood.HUNGRY
    reaction = state.latest_reaction
    if reaction is not None and now_utc < reaction.expires_at:
        return Mood.HAPPY
    return Mood.IDLE


def _require_aware(now_utc: datetime) -> None:
    if now_utc.tzinfo is None or now_utc.utcoffset() is None:
        raise ValueError("now_utc must be timezone-aware")
