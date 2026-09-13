"""Semantic control intents, domain commands and decision results."""

from dataclasses import dataclass
from enum import StrEnum

from deskpet.core.events import EventDraft
from deskpet.core.models import RejectionCode


class ActionId(StrEnum):
    OPEN_FEED = "open_feed"
    FEED_DEFAULT = "open_feed"  # compatibility alias for pre-M25 callers
    BUY_JOLLOF = "buy_jollof"
    BUY_COFFEE = "buy_coffee"
    PET = "pet"
    OPEN_SETUP = "open_setup"
    CYCLE_DURATION = "cycle_duration"
    CONFIRM_FOCUS = "confirm_focus"
    END_CURRENT = "end_current"
    END_BREAK = "end_break"
    PAUSE_CURRENT = "pause_current"
    RESUME_CURRENT = "resume_current"
    SKIP_BREAK = "skip_break"
    START_BREAK = "start_break"
    BACK_HOME = "back_home"
    SHOW_TIME = "show_time"
    RESTART_FOCUS = "restart_focus"
    OPEN_SETTINGS = "open_settings"
    CYCLE_SETTING = "cycle_setting"
    TOGGLE_SETTING = "toggle_setting"


@dataclass(frozen=True, slots=True)
class OpenFeed: ...


FeedDefault = OpenFeed


@dataclass(frozen=True, slots=True)
class BuyItem:
    item_id: str


@dataclass(frozen=True, slots=True)
class PetOnce: ...


@dataclass(frozen=True, slots=True)
class OpenSetup: ...


@dataclass(frozen=True, slots=True)
class CycleDuration: ...


@dataclass(frozen=True, slots=True)
class ConfirmFocus: ...


@dataclass(frozen=True, slots=True)
class EndCurrent: ...


@dataclass(frozen=True, slots=True)
class PauseCurrent: ...


@dataclass(frozen=True, slots=True)
class ResumeCurrent: ...


@dataclass(frozen=True, slots=True)
class SkipBreakIntent: ...


@dataclass(frozen=True, slots=True)
class StartBreakIntent: ...


@dataclass(frozen=True, slots=True)
class BackHome: ...


@dataclass(frozen=True, slots=True)
class ShowTime: ...


@dataclass(frozen=True, slots=True)
class RestartFocus: ...


@dataclass(frozen=True, slots=True)
class OpenSettings: ...


@dataclass(frozen=True, slots=True)
class CycleSetting: ...


@dataclass(frozen=True, slots=True)
class ToggleSetting: ...


type ControlIntent = (
    OpenFeed
    | BuyItem
    | PetOnce
    | PetOnce
    | OpenSetup
    | CycleDuration
    | ConfirmFocus
    | EndCurrent
    | PauseCurrent
    | ResumeCurrent
    | SkipBreakIntent
    | StartBreakIntent
    | BackHome
    | ShowTime
    | RestartFocus
    | OpenSettings
    | CycleSetting
    | ToggleSetting
)


@dataclass(frozen=True, slots=True)
class FeedPet:
    food_id: str
    operation_key: str


@dataclass(frozen=True, slots=True)
class StartFocus:
    session_id: str
    minutes: int


@dataclass(frozen=True, slots=True)
class StartBreak:
    session_id: str
    parent_focus_id: str


@dataclass(frozen=True, slots=True)
class PauseSession:
    session_id: str
    operation_key: str


@dataclass(frozen=True, slots=True)
class ResumeSession:
    session_id: str
    operation_key: str


class RequestedEndReason(StrEnum):
    USER = "user"
    APP_RESTART = "app_restart"
    APP_SHUTDOWN = "app_shutdown"
    SUSPEND = "suspend"
    STORAGE_RECOVERY = "storage_recovery"


@dataclass(frozen=True, slots=True)
class EndSession:
    session_id: str
    reason: RequestedEndReason


@dataclass(frozen=True, slots=True)
class CompleteSession:
    session_id: str


@dataclass(frozen=True, slots=True)
class SkipBreak:
    parent_focus_id: str


type DomainCommand = (
    FeedPet
    | StartFocus
    | StartBreak
    | PauseSession
    | ResumeSession
    | EndSession
    | CompleteSession
    | SkipBreak
)


@dataclass(frozen=True, slots=True)
class Accepted:
    event: EventDraft


@dataclass(frozen=True, slots=True)
class Rejected:
    code: RejectionCode


@dataclass(frozen=True, slots=True)
class NoOp: ...


type Decision = Accepted | Rejected | NoOp
