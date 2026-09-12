"""Immutable domain and runtime records for the desk pet."""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import NewType

ButtonId = NewType("ButtonId", int)


class Screen(StrEnum):
    HOME = "home"
    SETUP = "setup"
    FOCUS = "focus"
    BREAK_OFFER = "break_offer"
    BREAK = "break"


class Mood(StrEnum):
    CALM = "calm"
    CONTENT = "content"
    HAPPY = "happy"
    SAD = "sad"
    FOCUSED = "focused"
    RESTING = "resting"


class ReactionMood(StrEnum):
    CONTENT = "content"
    HAPPY = "happy"
    SAD = "sad"


class SessionKind(StrEnum):
    FOCUS = "focus"
    BREAK = "break"


class SessionStatus(StrEnum):
    RUNNING = "running"
    PAUSED = "paused"


class Gesture(StrEnum):
    PRESS = "press"
    HOLD = "hold"


class RejectionCode(StrEnum):
    UNAVAILABLE = "unavailable"
    INVALID_DURATION = "invalid_duration"
    INVALID_FOOD = "invalid_food"
    NO_SESSION = "no_session"
    WRONG_SESSION_STATE = "wrong_session_state"
    NO_BREAK_OFFER = "no_break_offer"


class PublishStatus(StrEnum):
    QUEUED = "queued"
    DROPPED = "dropped"
    DISCONNECTED = "disconnected"


class Feedback(StrEnum):
    UNAVAILABLE = "unavailable"
    STORAGE_ERROR = "storage_error"


@dataclass(frozen=True, slots=True)
class FoodDefinition:
    id: str
    sprite_id: str
    content_seconds: int

    def __post_init__(self) -> None:
        _require_text(self.id, "food id")
        _require_text(self.sprite_id, "sprite id")
        _require_positive(self.content_seconds, "content_seconds")


@dataclass(frozen=True, slots=True)
class Reaction:
    mood: ReactionMood
    expires_at: datetime

    def __post_init__(self) -> None:
        _require_aware(self.expires_at, "expires_at")


@dataclass(frozen=True, slots=True)
class FocusTerms:
    duration_seconds: int
    break_seconds: int
    grace_active_ms: int
    sad_seconds: int
    happy_seconds: int
    report_timezone: str

    def __post_init__(self) -> None:
        _require_positive(self.duration_seconds, "duration_seconds")
        _require_positive(self.break_seconds, "break_seconds")
        _require_nonnegative(self.grace_active_ms, "grace_active_ms")
        _require_positive(self.sad_seconds, "sad_seconds")
        _require_positive(self.happy_seconds, "happy_seconds")
        _require_text(self.report_timezone, "report_timezone")


@dataclass(frozen=True, slots=True)
class BreakTerms:
    duration_seconds: int
    parent_focus_id: str
    report_timezone: str

    def __post_init__(self) -> None:
        _require_positive(self.duration_seconds, "duration_seconds")
        _require_text(self.parent_focus_id, "parent_focus_id")
        _require_text(self.report_timezone, "report_timezone")


@dataclass(frozen=True, slots=True)
class BreakOffer:
    parent_focus_id: str
    duration_seconds: int
    report_timezone: str

    def __post_init__(self) -> None:
        _require_text(self.parent_focus_id, "parent_focus_id")
        _require_positive(self.duration_seconds, "duration_seconds")
        _require_text(self.report_timezone, "report_timezone")


SessionTerms = FocusTerms | BreakTerms


@dataclass(frozen=True, slots=True)
class Session:
    id: str
    kind: SessionKind
    terms: SessionTerms
    status: SessionStatus
    committed_active_ms: int

    def __post_init__(self) -> None:
        _require_text(self.id, "session id")
        _require_nonnegative(self.committed_active_ms, "committed_active_ms")
        mismatched = (
            self.kind is SessionKind.FOCUS and not isinstance(self.terms, FocusTerms)
        ) or (self.kind is SessionKind.BREAK and not isinstance(self.terms, BreakTerms))
        if mismatched:
            raise ValueError("session kind and terms do not match")
        if self.committed_active_ms > self.terms.duration_seconds * 1_000:
            raise ValueError("committed_active_ms exceeds duration")


@dataclass(frozen=True, slots=True)
class GameState:
    user_id: str
    pet_id: str
    active_session: Session | None = None
    pending_break: BreakOffer | None = None
    last_focus_minutes: int | None = None
    latest_reaction: Reaction | None = None
    focus_dates: frozenset[date] = field(default_factory=lambda: frozenset[date]())
    last_seq: int = 0

    def __post_init__(self) -> None:
        _require_text(self.user_id, "user_id")
        _require_text(self.pet_id, "pet_id")
        _require_nonnegative(self.last_seq, "last_seq")
        if self.active_session is not None and self.pending_break is not None:
            raise ValueError("active_session and pending_break are mutually exclusive")
        if self.last_focus_minutes is not None:
            _require_positive(self.last_focus_minutes, "last_focus_minutes")


@dataclass(frozen=True, slots=True)
class ClockReading:
    utc: datetime
    monotonic_ms: int
    resumed: bool

    def __post_init__(self) -> None:
        _require_aware(self.utc, "utc")
        _require_nonnegative(self.monotonic_ms, "monotonic_ms")


@dataclass(frozen=True, slots=True)
class RuntimeState:
    screen: Screen
    selected_focus_minutes: int
    run_anchor_mono_ms: int | None
    previous_clock: ClockReading | None
    control_epoch: int
    connection_id: str | None
    boot_id: str | None

    def __post_init__(self) -> None:
        _require_positive(self.selected_focus_minutes, "selected_focus_minutes")
        _require_positive(self.control_epoch, "control_epoch")
        if self.run_anchor_mono_ms is not None:
            _require_nonnegative(self.run_anchor_mono_ms, "run_anchor_mono_ms")


@dataclass(frozen=True, slots=True)
class TimerSample:
    session_id: str
    active_ms: int
    remaining_seconds: int
    due: bool

    def __post_init__(self) -> None:
        _require_text(self.session_id, "session_id")
        _require_nonnegative(self.active_ms, "active_ms")
        _require_nonnegative(self.remaining_seconds, "remaining_seconds")


@dataclass(frozen=True, slots=True)
class DailyFocusTotal:
    day: date
    completed_count: int
    completed_seconds: int


@dataclass(frozen=True, slots=True)
class WeeklyReport:
    week_start: date
    timezone: str
    completed_focus_count: int
    completed_focus_seconds: int
    early_end_count: int
    early_end_active_ms: int
    interrupted_count: int
    interrupted_recorded_active_ms: int
    break_count: int
    feed_count: int
    daily_totals: tuple[DailyFocusTotal, ...]
    current_streak: int


def _require_text(value: str, name: str) -> None:
    if not value:
        raise ValueError(f"{name} must not be empty")


def _require_positive(value: int, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def _require_nonnegative(value: int, name: str) -> None:
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
