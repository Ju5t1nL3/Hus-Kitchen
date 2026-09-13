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
    FocusRewardGranted,
    FocusSessionCompleted,
    FocusSessionEnded,
    FocusSessionPaused,
    FocusSessionResumed,
    FocusSessionStarted,
    ItemPurchasedAndFed,
    PetComforted,
    PetCreated,
    PetFed,
    ProgressionInitialized,
    TrackingPreferencesChanged,
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
    level_for_xp,
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
            last_fed_at=event.event.occurred_at,
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
                    xp_level_increment=draft.xp_level_increment,
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
        case ItemPurchasedAndFed():
            if state.active_session is not None or state.pending_break is not None:
                raise ReplayError(
                    "purchase is unavailable during a session or break offer"
                )
            progression = state.progression
            if not draft.item_id:
                raise ReplayError("purchase item_id must not be empty")
            if progression is None:
                raise ReplayError("purchase requires initialized progression")
            if draft.price_paid <= 0:
                raise ReplayError("purchase price must be positive")
            expected_balance = progression.yarn_balance - draft.price_paid
            if expected_balance < 0 or draft.yarn_balance_after != expected_balance:
                raise ReplayError("purchase yarn balance does not match recorded price")
            _require_reaction(draft.reaction, ReactionMood.HAPPY, "purchase")
            return _advance(
                state,
                event,
                progression=replace(progression, yarn_balance=draft.yarn_balance_after),
                latest_reaction=draft.reaction,
                last_fed_at=event.event.occurred_at,
            )
        case PetComforted():
            if not state.needs_comfort:
                raise ReplayError("pet_comforted requires a sad pet")
            _require_reaction(draft.reaction, ReactionMood.HAPPY, "comfort")
            return _advance(
                state,
                event,
                needs_comfort=False,
                latest_reaction=draft.reaction,
            )
        case TrackingPreferencesChanged():
            return _advance(
                state,
                event,
                keyboard_tracking_enabled=draft.keyboard_enabled,
                camera_tracking_enabled=draft.camera_enabled,
            )
        case FocusRewardGranted():
            progression = state.progression
            offer = state.pending_break
            if progression is None or offer is None:
                raise ReplayError("focus reward requires progression and break offer")
            if offer.parent_focus_id != draft.focus_session_id:
                raise ReplayError("focus reward does not match latest completion")
            values = (
                draft.policy_version,
                draft.chain_number,
                draft.focus_minutes,
                draft.base_xp,
                draft.base_yarn,
            )
            if any(value <= 0 for value in values):
                raise ReplayError("focus reward positive fields are invalid")
            if draft.chain_xp < 0 or draft.chain_yarn < 0:
                raise ReplayError("focus reward chain fields are invalid")
            if draft.keyboard_keypresses < 0 or draft.keyboard_yarn not in (0, 1, 2):
                raise ReplayError("focus reward keyboard fields are invalid")
            if (
                not draft.keyboard_enabled
                and (
                    draft.keyboard_available
                    or draft.keyboard_keypresses
                    or draft.keyboard_yarn
                )
            ) or (
                not draft.keyboard_available
                and (draft.keyboard_keypresses or draft.keyboard_yarn)
            ):
                raise ReplayError("focus reward keyboard eligibility is inconsistent")
            camera_counts = (
                draft.camera_attempted_samples,
                draft.camera_observed_samples,
                draft.camera_attentive_samples,
            )
            if any(value < 0 for value in camera_counts) or draft.camera_yarn not in (
                0,
                1,
                2,
            ):
                raise ReplayError("focus reward camera fields are invalid")
            if (
                draft.camera_observed_samples > draft.camera_attempted_samples
                or draft.camera_attentive_samples > draft.camera_observed_samples
            ):
                raise ReplayError("focus reward camera sample counts are inconsistent")
            if (
                not draft.camera_enabled
                and (draft.camera_available or any(camera_counts) or draft.camera_yarn)
            ) or (
                not draft.camera_available and (any(camera_counts) or draft.camera_yarn)
            ):
                raise ReplayError("focus reward camera eligibility is inconsistent")
            if (
                draft.total_xp_before != progression.total_xp
                or draft.level_before != progression.level
                or draft.yarn_before != progression.yarn_balance
            ):
                raise ReplayError("focus reward before totals do not match state")
            if (
                draft.total_xp_after
                != draft.total_xp_before + draft.base_xp + draft.chain_xp
            ):
                raise ReplayError("focus reward XP breakdown does not add up")
            if (
                draft.yarn_after
                != draft.yarn_before
                + draft.base_yarn
                + draft.chain_yarn
                + draft.keyboard_yarn
                + draft.camera_yarn
            ):
                raise ReplayError("focus reward yarn breakdown does not add up")
            expected_level = level_for_xp(
                draft.total_xp_after,
                progression.xp_per_level,
                progression.xp_level_increment,
            )
            if draft.level_after != expected_level:
                raise ReplayError("focus reward level does not match XP")
            return _advance(
                state,
                event,
                progression=replace(
                    progression,
                    total_xp=draft.total_xp_after,
                    level=draft.level_after,
                    yarn_balance=draft.yarn_after,
                ),
            )
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
            if draft.reason is EndReason.USER_EARLY:
                changes["needs_comfort"] = True
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
