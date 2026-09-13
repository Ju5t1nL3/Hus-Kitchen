"""Typed device inputs, render snapshots and application-level results."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from deskpet.core.commands import ActionId, ControlIntent
from deskpet.core.models import (
    ButtonId,
    ClockReading,
    Feedback,
    GameState,
    Gesture,
    Mood,
    Screen,
    TimerSample,
)


class ControlContext(StrEnum):
    HOME = "home"
    FEED = "feed"
    SETUP = "setup"
    FOCUS_RUNNING = "focus_running"
    FOCUS_PAUSED = "focus_paused"
    BREAK_OFFER = "break_offer"
    BREAK_RUNNING = "break_running"
    SETTINGS = "settings"


@dataclass(frozen=True, slots=True)
class DeviceReady:
    connection_id: str | None
    boot_id: str
    buttons: tuple[ButtonId, ...]
    ui: str


@dataclass(frozen=True, slots=True)
class ButtonInput:
    connection_id: str
    boot_id: str
    seq: int
    control_epoch: int
    button: ButtonId
    action: Gesture
    received_at: ClockReading


@dataclass(frozen=True, slots=True)
class Pong:
    connection_id: str
    nonce: int


@dataclass(frozen=True, slots=True)
class ConnectionChanged:
    connection_id: str
    connected: bool


@dataclass(frozen=True, slots=True)
class Tick:
    clock: ClockReading


@dataclass(frozen=True, slots=True)
class Shutdown: ...


type DeviceMessage = DeviceReady | ButtonInput | Pong
type InputMessage = DeviceMessage | ConnectionChanged | Tick | Shutdown


@dataclass(frozen=True, slots=True)
class ButtonLabel:
    button: ButtonId
    label: str
    enabled: bool


@dataclass(frozen=True, slots=True)
class ProgressionView:
    level: int
    xp_into_level: int
    xp_for_next_level: int
    yarn_balance: int

    def __post_init__(self) -> None:
        if self.level <= 0 or self.xp_for_next_level <= 0:
            raise ValueError("progression level and threshold must be positive")
        if not 0 <= self.xp_into_level < self.xp_for_next_level:
            raise ValueError("xp_into_level must be within the current level")
        if self.yarn_balance < 0:
            raise ValueError("yarn_balance must be nonnegative")


@dataclass(frozen=True, slots=True)
class EarnedRewardsView:
    xp: int
    yarn: int

    def __post_init__(self) -> None:
        if self.xp < 0 or self.yarn < 0:
            raise ValueError("earned rewards must be nonnegative")


@dataclass(frozen=True, slots=True)
class SettingsView:
    selected_row: int
    keyboard_enabled: bool
    keyboard_available: bool
    camera_enabled: bool
    camera_available: bool

    def __post_init__(self) -> None:
        if self.selected_row not in (0, 1):
            raise ValueError("selected_row must select keyboard or camera")


type AvailabilityPredicate = Callable[[GameState], bool]


@dataclass(frozen=True, slots=True)
class ActionDefinition:
    id: ActionId
    label: str
    intent: ControlIntent
    available: AvailabilityPredicate


type BindingKey = tuple[ControlContext, ButtonId, Gesture]
type ControlBindings = Mapping[BindingKey, ActionId]


@dataclass(frozen=True, slots=True)
class RenderSnapshot:
    screen: Screen
    control_epoch: int
    mood: Mood
    clock_text: str | None
    timer_seconds: int | None
    paused: bool
    focus_minutes: int | None
    break_minutes: int | None
    buttons: tuple[ButtonLabel, ...]
    feedback: Feedback | None
    progression: ProgressionView | None = None
    earned_rewards: EarnedRewardsView | None = None
    settings: SettingsView | None = None


class AnimationName(StrEnum):
    FEED = "feed"
    CELEBRATE = "celebrate"


@dataclass(frozen=True, slots=True)
class CueRequest:
    name: AnimationName
    food_sprite: str | None


@dataclass(frozen=True, slots=True)
class AnimationCue:
    animation_id: str
    name: AnimationName
    after_revision: int
    food_sprite: str | None


@dataclass(frozen=True, slots=True)
class Parsed:
    message: DeviceMessage


@dataclass(frozen=True, slots=True)
class Invalid:
    code: str


type ParseResult = Parsed | Invalid


@dataclass(frozen=True, slots=True)
class NormalSchedule:
    sample: TimerSample | None
    next_wake_mono_ms: int


@dataclass(frozen=True, slots=True)
class InterruptedSchedule:
    session_id: str | None
    reason: str = "suspend"


type ScheduleResult = NormalSchedule | InterruptedSchedule


@dataclass(frozen=True, slots=True)
class PresentationResult:
    screen: Screen
    cues: tuple[CueRequest, ...]
