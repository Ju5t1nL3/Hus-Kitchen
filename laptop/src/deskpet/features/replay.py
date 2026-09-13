"""Pure reconstruction of durable game state from committed events."""

from collections.abc import Iterable
from dataclasses import replace
from typing import assert_never

from deskpet.core.events import (
    EVENT_SCHEMA_VERSION,
    BreakSessionCompleted,
    BreakSessionEnded,
    BreakSessionStarted,
    BreakSkipped,
    DomainEvent,
    EndReason,
    FocusSessionCompleted,
    FocusSessionEnded,
    FocusSessionPaused,
    FocusSessionResumed,
    FocusSessionStarted,
    PetCreated,
    PetFed,
    ProgressionInitialized,
)
from deskpet.core.models import (
    FocusTerms,
    GameState,
    ProgressionState,
    Reaction,
    ReactionMood,
    Session,
    SessionKind,
    SessionStatus,
)


class ReplayError(ValueError):
    """Raised when committed history violates the event model."""


def rebuild(events: Iterable[DomainEvent]) -> GameState | None:
    """Apply already ordered history through the same incremental reducer."""
    state: GameState | None = None
    for event in events:
        state = apply_event(state, event)
    return state


def apply_event(state: GameState | None, event: DomainEvent) -> GameState:
    """Validate and immutably apply one committed event."""
    _validate_envelope(state, event)
    draft = event.event.draft

    if state is None:
        if not isinstance(draft, PetCreated):
            raise ReplayError("history must begin with pet_created")
        if not draft.pet_id:
            raise ReplayError("pet_created has an empty pet_id")
        return GameState(
            user_id=event.event.user_id,
            pet_id=draft.pet_id,
            last_seq=event.seq,
        )

    match draft:
        case PetCreated():
            raise ReplayError("history contains more than one pet_created event")
        case ProgressionInitialized():
            if state.progression is not None:
                raise ReplayError("progression can only be initialized once")
            try:
                progression = ProgressionState(
                    total_xp=0,
                    level=1,
                    yarn_balance=draft.starting_yarn,
                    policy_version=draft.policy_version,
                    xp_per_level=draft.xp_per_level,
                )
            except ValueError as error:
                raise ReplayError(
                    f"invalid progression initialization: {error}"
                ) from error
            return _advance(state, event, progression=progression)
        case PetFed():
            if state.active_session is not None or state.pending_break is not None:
                raise ReplayError(
                    "pet_fed is unavailable during a session or break offer"
                )
            return _advance(state, event, latest_reaction=draft.reaction)
        case FocusSessionStarted():
            _require_available(state, "focus session start")
            if draft.terms.duration_seconds % 60 != 0:
                raise ReplayError("focus duration must be a whole number of minutes")
            session = Session(
                id=draft.session_id,
                kind=SessionKind.FOCUS,
                terms=draft.terms,
                status=SessionStatus.RUNNING,
                committed_active_ms=0,
            )
            return _advance(
                state,
                event,
                active_session=session,
                last_focus_minutes=draft.terms.duration_seconds // 60,
            )
        case BreakSessionStarted():
            if state.active_session is not None:
                raise ReplayError("break cannot start while a session is active")
            offer = state.pending_break
            if offer is None:
                raise ReplayError("break start requires a pending break offer")
            if (
                offer.parent_focus_id != draft.terms.parent_focus_id
                or offer.duration_seconds != draft.terms.duration_seconds
                or offer.report_timezone != draft.terms.report_timezone
            ):
                raise ReplayError("break start does not match the pending offer")
            session = Session(
                id=draft.session_id,
                kind=SessionKind.BREAK,
                terms=draft.terms,
                status=SessionStatus.RUNNING,
                committed_active_ms=0,
            )
            return _advance(state, event, active_session=session, pending_break=None)
        case FocusSessionPaused():
            session = _require_session(
                state, draft.session_id, draft.kind, SessionStatus.RUNNING
            )
            _require_progress(session, draft.active_ms, terminal=False)
            return _advance(
                state,
                event,
                active_session=replace(
                    session,
                    status=SessionStatus.PAUSED,
                    committed_active_ms=draft.active_ms,
                ),
            )
        case FocusSessionResumed():
            session = _require_session(
                state, draft.session_id, draft.kind, SessionStatus.PAUSED
            )
            if draft.active_ms != session.committed_active_ms:
                raise ReplayError("resume active_ms must equal the paused value")
            return _advance(
                state,
                event,
                active_session=replace(session, status=SessionStatus.RUNNING),
            )
        case FocusSessionCompleted():
            session = _require_session(
                state, draft.session_id, SessionKind.FOCUS, SessionStatus.RUNNING
            )
            _require_completion(session, draft.active_ms)
            terms = _focus_terms(session)
            if (
                draft.break_offer.parent_focus_id != session.id
                or draft.break_offer.duration_seconds != terms.break_seconds
                or draft.break_offer.report_timezone != terms.report_timezone
            ):
                raise ReplayError(
                    "focus completion break offer does not match its terms"
                )
            _require_reaction(draft.reaction, ReactionMood.HAPPY, "focus completion")
            return _advance(
                state,
                event,
                active_session=None,
                pending_break=draft.break_offer,
                latest_reaction=draft.reaction,
                focus_dates=state.focus_dates | {draft.credit_date},
            )
        case BreakSessionCompleted():
            session = _require_session(
                state, draft.session_id, SessionKind.BREAK, SessionStatus.RUNNING
            )
            _require_completion(session, draft.active_ms)
            return _advance(state, event, active_session=None)
        case FocusSessionEnded():
            session = _require_session(state, draft.session_id, SessionKind.FOCUS)
            _require_progress(session, draft.active_ms, terminal=True)
            _validate_focus_end(draft.reason, draft.reaction, draft.active_ms, session)
            changes: dict[str, object] = {"active_session": None}
            if draft.reaction is not None:
                changes["latest_reaction"] = draft.reaction
            return _advance(state, event, **changes)
        case BreakSessionEnded():
            session = _require_session(state, draft.session_id, SessionKind.BREAK)
            _require_progress(session, draft.active_ms, terminal=True)
            if draft.reason not in {
                EndReason.USER_BREAK,
                EndReason.APP_RESTART,
                EndReason.APP_SHUTDOWN,
                EndReason.SUSPEND,
                EndReason.STORAGE_RECOVERY,
            }:
                raise ReplayError("break ended with an invalid reason")
            return _advance(state, event, active_session=None)
        case BreakSkipped():
            if state.active_session is not None:
                raise ReplayError("break cannot be skipped while a session is active")
            offer = state.pending_break
            if offer is None or offer.parent_focus_id != draft.parent_focus_id:
                raise ReplayError("break skip does not match the pending offer")
            return _advance(state, event, pending_break=None)
        case _ as unreachable:
            assert_never(unreachable)


def _validate_envelope(state: GameState | None, event: DomainEvent) -> None:
    if event.event.schema_version != EVENT_SCHEMA_VERSION:
        raise ReplayError(f"unsupported event schema version at seq {event.seq}")
    if not event.event.user_id:
        raise ReplayError(f"event at seq {event.seq} has an empty user_id")
    if state is None:
        return
    if event.seq <= state.last_seq:
        raise ReplayError("event sequence must be strictly increasing")
    if event.event.user_id != state.user_id:
        raise ReplayError("event user_id does not match the existing game state")


def _advance(state: GameState, event: DomainEvent, **changes: object) -> GameState:
    return replace(state, last_seq=event.seq, **changes)


def _require_available(state: GameState, action: str) -> None:
    if state.active_session is not None or state.pending_break is not None:
        raise ReplayError(f"{action} is unavailable")


def _require_session(
    state: GameState,
    session_id: str,
    kind: SessionKind,
    status: SessionStatus | None = None,
) -> Session:
    session = state.active_session
    if session is None:
        raise ReplayError("session event has no active session")
    if session.id != session_id or session.kind is not kind:
        raise ReplayError("session event does not match the active session")
    if status is not None and session.status is not status:
        raise ReplayError(f"session must be {status.value}")
    return session


def _require_progress(session: Session, active_ms: int, *, terminal: bool) -> None:
    duration_ms = session.terms.duration_seconds * 1_000
    if active_ms < session.committed_active_ms:
        raise ReplayError("session active_ms cannot decrease")
    if active_ms >= duration_ms:
        label = "terminal" if terminal else "pause"
        raise ReplayError(f"{label} active_ms must be below session duration")
    if (
        session.status is SessionStatus.PAUSED
        and active_ms != session.committed_active_ms
    ):
        raise ReplayError("paused session active_ms must equal its saved value")


def _require_completion(session: Session, active_ms: int) -> None:
    if active_ms != session.terms.duration_seconds * 1_000:
        raise ReplayError("completion active_ms must equal session duration")


def _focus_terms(session: Session) -> FocusTerms:
    if not isinstance(session.terms, FocusTerms):
        raise ReplayError("focus session has invalid terms")
    return session.terms


def _validate_focus_end(
    reason: EndReason,
    reaction: Reaction | None,
    active_ms: int,
    session: Session,
) -> None:
    terms = _focus_terms(session)
    if reason is EndReason.USER_GRACE:
        if active_ms >= terms.grace_active_ms or reaction is not None:
            raise ReplayError("user_grace must be below grace with no reaction")
        return
    if reason is EndReason.USER_EARLY:
        if active_ms < terms.grace_active_ms or reaction is None:
            raise ReplayError("user_early must be at/after grace with a reaction")
        _require_reaction(reaction, ReactionMood.SAD, "early focus end")
        return
    if (
        reason
        not in {
            EndReason.APP_RESTART,
            EndReason.APP_SHUTDOWN,
            EndReason.SUSPEND,
            EndReason.STORAGE_RECOVERY,
        }
        or reaction is not None
    ):
        raise ReplayError("focus ended with an invalid reason or reaction")


def _require_reaction(reaction: Reaction, expected: ReactionMood, context: str) -> None:
    if reaction.mood is not expected:
        raise ReplayError(f"{context} requires a {expected.value} reaction")
