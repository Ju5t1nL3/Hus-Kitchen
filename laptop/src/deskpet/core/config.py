"""Immutable, validated laptop configuration records."""

from collections.abc import Mapping
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from deskpet.core.models import FoodDefinition
from deskpet.core.views import AnimationName, ControlBindings


@dataclass(frozen=True, slots=True)
class IdentityConfig:
    user_id: str
    pet_id: str
    device_id: str

    def __post_init__(self) -> None:
        _text(self.user_id, "identity.user_id")
        _text(self.pet_id, "identity.pet_id")
        _text(self.device_id, "identity.device_id")


@dataclass(frozen=True, slots=True)
class FocusConfig:
    allowed_minutes: tuple[int, ...]
    default_minutes: int
    focus_minutes_per_break_minute: int
    minimum_break_minutes: int
    grace_active_seconds: int
    happy_seconds: int
    sad_seconds: int
    report_timezone: str

    def __post_init__(self) -> None:
        if tuple(sorted(set(self.allowed_minutes))) != self.allowed_minutes:
            raise ValueError("focus.allowed_minutes must be sorted and unique")
        if not self.allowed_minutes or any(
            value < 5 or value > 60 or value % 5 for value in self.allowed_minutes
        ):
            raise ValueError(
                "focus.allowed_minutes must be 5-minute steps from 5 through 60"
            )
        if self.default_minutes not in self.allowed_minutes:
            raise ValueError("focus.default_minutes must be allowed")
        _positive(
            self.focus_minutes_per_break_minute,
            "focus.focus_minutes_per_break_minute",
        )
        _positive(self.minimum_break_minutes, "focus.minimum_break_minutes")
        if self.grace_active_seconds < 0:
            raise ValueError("focus.grace_active_seconds must be nonnegative")
        _positive(self.happy_seconds, "focus.happy_seconds")
        _positive(self.sad_seconds, "focus.sad_seconds")
        _timezone(self.report_timezone, "focus.report_timezone")


@dataclass(frozen=True, slots=True)
class FeedingConfig:
    definitions: Mapping[str, FoodDefinition]
    hunger_seconds: int

    def __post_init__(self) -> None:
        if not self.definitions:
            raise ValueError("feeding.definitions must not be empty")
        _positive(self.hunger_seconds, "feeding.hunger_seconds")
        for food_id, definition in self.definitions.items():
            if food_id != definition.id:
                raise ValueError("feeding definition key and id must match")
            if definition.display_name is None or definition.price_yarn <= 0:
                raise ValueError("configured feeding items require a name and price")
            try:
                AnimationName(definition.consume_animation)
            except ValueError as error:
                raise ValueError("feeding item has an unknown animation") from error


@dataclass(frozen=True, slots=True)
class UiConfig:
    clock_timezone: str
    max_buttons: int

    def __post_init__(self) -> None:
        _timezone(self.clock_timezone, "ui.clock_timezone")
        _positive(self.max_buttons, "ui.max_buttons")


@dataclass(frozen=True, slots=True)
class DeviceConfig:
    port: str | None
    usb_vid: int | None
    usb_pid: int | None
    serial_number: str | None

    def __post_init__(self) -> None:
        for value, name in (
            (self.usb_vid, "device.usb_vid"),
            (self.usb_pid, "device.usb_pid"),
        ):
            if value is not None and not 0 <= value <= 0xFFFF:
                raise ValueError(f"{name} must be a 16-bit USB ID")
        if self.port is not None:
            _text(self.port, "device.port")
        if self.serial_number is not None:
            _text(self.serial_number, "device.serial_number")


@dataclass(frozen=True, slots=True)
class ProgressionConfig:
    policy_version: int
    starting_yarn: int
    xp_per_level: int

    def __post_init__(self) -> None:
        _positive(self.policy_version, "progression.policy_version")
        if self.starting_yarn < 0:
            raise ValueError("progression.starting_yarn must be nonnegative")
        _positive(self.xp_per_level, "progression.xp_per_level")


@dataclass(frozen=True, slots=True)
class AppConfig:
    identity: IdentityConfig
    focus: FocusConfig
    feeding: FeedingConfig
    bindings: ControlBindings
    ui: UiConfig
    device: DeviceConfig
    progression: ProgressionConfig


def _text(value: str, path: str) -> None:
    if not value.strip():
        raise ValueError(f"{path} must not be empty")


def _positive(value: int, path: str) -> None:
    if value <= 0:
        raise ValueError(f"{path} must be positive")


def _timezone(value: str, path: str) -> None:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"{path} must be a known IANA timezone") from error
