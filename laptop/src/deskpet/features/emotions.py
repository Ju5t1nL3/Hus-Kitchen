"""Pure selection of the pet's visible mood."""

from datetime import datetime

from deskpet.core.models import GameState, Mood, SessionKind, SessionStatus


def select(state: GameState, now_utc: datetime) -> Mood:
    """Return the newest active reaction or the current activity's default mood."""
    _require_aware(now_utc)
    reaction = state.latest_reaction
    if reaction is not None and now_utc < reaction.expires_at:
        return Mood(reaction.mood.value)

    session = state.active_session
    if session is None or session.status is SessionStatus.PAUSED:
        return Mood.CALM
    if session.kind is SessionKind.FOCUS:
        return Mood.FOCUSED
    return Mood.RESTING


def _require_aware(now_utc: datetime) -> None:
    if now_utc.tzinfo is None or now_utc.utcoffset() is None:
        raise ValueError("now_utc must be timezone-aware")
