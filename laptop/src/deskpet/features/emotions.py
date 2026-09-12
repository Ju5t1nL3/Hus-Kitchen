"""Pure mood selection from recorded state (M07's emotion half).

This is a query over already-recorded facts, not a stat model: no decay log,
offline penalty or emotion score exists. See docs/event_model.md's "Replay and
emotion selection" section for the exact contract implemented here.
"""

from datetime import datetime

from deskpet.core.models import GameState, Mood, SessionKind, SessionStatus


def select(state: GameState, now_utc: datetime) -> Mood:
    """Return the current mood: the latest unexpired reaction, else activity default."""
    reaction = state.latest_reaction
    if reaction is not None and reaction.expires_at > now_utc:
        return Mood(reaction.mood.value)

    session = state.active_session
    if session is not None and session.status is SessionStatus.RUNNING:
        return Mood.FOCUSED if session.kind is SessionKind.FOCUS else Mood.RESTING

    return Mood.CALM
