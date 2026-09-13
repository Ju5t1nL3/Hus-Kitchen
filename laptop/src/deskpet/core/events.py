"""Typed event drafts and durable event envelopes."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import ClassVar, Literal
from uuid import UUID

from deskpet.core.models import (
    BreakOffer,
    BreakTerms,
    FocusTerms,
    Reaction,
    SessionKind,
)

EVENT_SCHEMA_VERSION: Literal[2] = 2


class EventSource(StrEnum):
    SYSTEM = "system"
    LOCAL_CONTROLS = "local_controls"


class EndReason(StrEnum):
    USER_GRACE = "user_grace"
    USER_EARLY = "user_early"
    USER_BREAK = "user_break"
    APP_RESTART = "app_restart"
    APP_SHUTDOWN = "app_shutdown"
    SUSPEND = "suspend"
    STORAGE_RECOVERY = "storage_recovery"


@dataclass(frozen=True, slots=True, kw_only=True)
class DraftMetadata:
    source: EventSource
    dedupe_key: str

    def __post_init__(self) -> None:
        if not self.dedupe_key:
            raise ValueError("dedupe_key must not be empty")


@dataclass(frozen=True, slots=True, kw_only=True)
class PetCreated(DraftMetadata):
    event_type: ClassVar[Literal["pet_created"]] = "pet_created"
    pet_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ProgressionInitialized(DraftMetadata):
    event_type: ClassVar[Literal["progression_initialized"]] = "progression_initialized"
    policy_version: int
    starting_yarn: int
    xp_per_level: int


@dataclass(frozen=True, slots=True, kw_only=True)
class PetFed(DraftMetadata):
    event_type: ClassVar[Literal["pet_fed"]] = "pet_fed"
    food_id: str
    reaction: Reaction


@dataclass(frozen=True, slots=True, kw_only=True)
class ItemPurchasedAndFed(DraftMetadata):
    event_type: ClassVar[Literal["item_purchased_and_fed"]] = "item_purchased_and_fed"
    item_id: str
    price_paid: int
    yarn_balance_after: int
    reaction: Reaction


@dataclass(frozen=True, slots=True, kw_only=True)
class PetComforted(DraftMetadata):
    event_type: ClassVar[Literal["pet_comforted"]] = "pet_comforted"
    reaction: Reaction


@dataclass(frozen=True, slots=True, kw_only=True)
class FocusSessionStarted(DraftMetadata):
    event_type: ClassVar[Literal["session_started"]] = "session_started"
    session_id: str
    kind: Literal[SessionKind.FOCUS] = SessionKind.FOCUS
    terms: FocusTerms


@dataclass(frozen=True, slots=True, kw_only=True)
class BreakSessionStarted(DraftMetadata):
    event_type: ClassVar[Literal["session_started"]] = "session_started"
    session_id: str
    kind: Literal[SessionKind.BREAK] = SessionKind.BREAK
    terms: BreakTerms


@dataclass(frozen=True, slots=True, kw_only=True)
class FocusSessionPaused(DraftMetadata):
    event_type: ClassVar[Literal["session_paused"]] = "session_paused"
    session_id: str
    active_ms: int
    kind: Literal[SessionKind.FOCUS] = SessionKind.FOCUS


@dataclass(frozen=True, slots=True, kw_only=True)
class FocusSessionResumed(DraftMetadata):
    event_type: ClassVar[Literal["session_resumed"]] = "session_resumed"
    session_id: str
    active_ms: int
    kind: Literal[SessionKind.FOCUS] = SessionKind.FOCUS


@dataclass(frozen=True, slots=True, kw_only=True)
class FocusSessionCompleted(DraftMetadata):
    event_type: ClassVar[Literal["session_completed"]] = "session_completed"
    session_id: str
    active_ms: int
    credit_date: date
    break_offer: BreakOffer
    reaction: Reaction
    kind: Literal[SessionKind.FOCUS] = SessionKind.FOCUS


@dataclass(frozen=True, slots=True, kw_only=True)
class BreakSessionCompleted(DraftMetadata):
    event_type: ClassVar[Literal["session_completed"]] = "session_completed"
    session_id: str
    active_ms: int
    kind: Literal[SessionKind.BREAK] = SessionKind.BREAK


@dataclass(frozen=True, slots=True, kw_only=True)
class FocusSessionEnded(DraftMetadata):
    event_type: ClassVar[Literal["session_ended"]] = "session_ended"
    session_id: str
    active_ms: int
    reason: EndReason
    reaction: Reaction | None
    kind: Literal[SessionKind.FOCUS] = SessionKind.FOCUS


@dataclass(frozen=True, slots=True, kw_only=True)
class BreakSessionEnded(DraftMetadata):
    event_type: ClassVar[Literal["session_ended"]] = "session_ended"
    session_id: str
    active_ms: int
    reason: EndReason
    kind: Literal[SessionKind.BREAK] = SessionKind.BREAK


@dataclass(frozen=True, slots=True, kw_only=True)
class BreakSkipped(DraftMetadata):
    event_type: ClassVar[Literal["break_skipped"]] = "break_skipped"
    parent_focus_id: str


type EventDraft = (
    PetCreated
    | ProgressionInitialized
    | PetFed
    | ItemPurchasedAndFed
    | PetComforted
    | FocusSessionStarted
    | BreakSessionStarted
    | FocusSessionPaused
    | FocusSessionResumed
    | FocusSessionCompleted
    | BreakSessionCompleted
    | FocusSessionEnded
    | BreakSessionEnded
    | BreakSkipped
)


@dataclass(frozen=True, slots=True)
class UncommittedEvent:
    event_id: UUID
    occurred_at: datetime
    user_id: str
    device_id: str
    draft: EventDraft
    schema_version: Literal[2] = EVENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class DomainEvent:
    seq: int
    event: UncommittedEvent

    def __post_init__(self) -> None:
        if self.seq <= 0:
            raise ValueError("seq must be positive")
