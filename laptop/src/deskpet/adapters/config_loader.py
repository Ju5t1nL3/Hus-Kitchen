"""YAML boundary for validated laptop configuration."""

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import cast

import yaml  # pyright: ignore[reportMissingModuleSource]

from deskpet.app.controls import ACTIONS, validate_bindings
from deskpet.core.commands import ActionId
from deskpet.core.config import (
    ActivityConfig,
    AppConfig,
    DeviceConfig,
    FeedingConfig,
    FocusConfig,
    IdentityConfig,
    ProgressionConfig,
    UiConfig,
)
from deskpet.core.models import ButtonId, FoodDefinition, Gesture
from deskpet.core.views import BindingKey, ControlBindings, ControlContext


class ConfigError(ValueError):
    """Raised when configuration cannot be read or validated."""


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects keys which would otherwise be overwritten."""


def _construct_unique_mapping(
    loader: yaml.SafeLoader, node: yaml.MappingNode, *, deep: bool = False
) -> dict[object, object]:
    loader.flatten_mapping(node)
    result: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = cast(
            object,
            loader.construct_object(  # pyright: ignore[reportUnknownMemberType]
                key_node, deep=deep
            ),
        )
        try:
            duplicate = key in result
        except TypeError as error:
            raise ConfigError("configuration mapping keys must be scalar") from error
        if duplicate:
            raise ConfigError(f"duplicate configuration key: {key}")
        result[key] = cast(
            object,
            loader.construct_object(  # pyright: ignore[reportUnknownMemberType]
                value_node, deep=deep
            ),
        )
    return result


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


def load(path: Path) -> AppConfig:
    """Read one YAML file and return only typed, immutable configuration."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigError(f"cannot read configuration {path}: {error}") from error
    try:
        raw = cast(object, yaml.load(text, Loader=_UniqueKeyLoader))
        config = _parse(_mapping(raw, "config"))
    except (yaml.YAMLError, TypeError, ValueError) as error:
        if isinstance(error, ConfigError):
            raise
        raise ConfigError(f"invalid configuration {path}: {error}") from error
    return config


def _parse(raw: Mapping[str, object]) -> AppConfig:
    _exact_keys(
        raw,
        {
            "identity",
            "focus",
            "feeding",
            "progression",
            "activity",
            "controls",
            "ui",
            "device",
        },
        "config",
    )
    identity = _mapping(_required(raw, "identity", "config"), "identity")
    focus = _mapping(_required(raw, "focus", "config"), "focus")
    feeding = _mapping(_required(raw, "feeding", "config"), "feeding")
    progression = _mapping(_required(raw, "progression", "config"), "progression")
    activity = _mapping(_required(raw, "activity", "config"), "activity")
    controls = _mapping(_required(raw, "controls", "config"), "controls")
    ui = _mapping(_required(raw, "ui", "config"), "ui")
    device = _mapping(_required(raw, "device", "config"), "device")

    config = AppConfig(
        identity=_identity(identity),
        focus=_focus(focus),
        feeding=_feeding(feeding),
        bindings=_bindings(controls),
        ui=_ui(ui),
        device=_device(device),
        progression=_progression(progression),
        activity=_activity(activity),
    )
    configured_buttons = tuple(
        sorted({button for _context, button, _gesture in config.bindings})
    )
    validate_bindings(config.bindings, configured_buttons, config.ui.max_buttons)
    return config


def _identity(raw: Mapping[str, object]) -> IdentityConfig:
    _exact_keys(raw, {"user_id", "pet_id", "device_id"}, "identity")
    return IdentityConfig(
        user_id=_string(_required(raw, "user_id", "identity"), "identity.user_id"),
        pet_id=_string(_required(raw, "pet_id", "identity"), "identity.pet_id"),
        device_id=_string(
            _required(raw, "device_id", "identity"), "identity.device_id"
        ),
    )


def _focus(raw: Mapping[str, object]) -> FocusConfig:
    expected = {
        "allowed_minutes",
        "default_minutes",
        "focus_minutes_per_break_minute",
        "minimum_break_minutes",
        "grace_active_seconds",
        "happy_seconds",
        "sad_seconds",
        "report_timezone",
    }
    _exact_keys(raw, expected, "focus")
    allowed = _list(_required(raw, "allowed_minutes", "focus"), "focus.allowed_minutes")
    return FocusConfig(
        allowed_minutes=tuple(
            _integer(value, f"focus.allowed_minutes[{index}]")
            for index, value in enumerate(allowed)
        ),
        default_minutes=_integer(
            _required(raw, "default_minutes", "focus"), "focus.default_minutes"
        ),
        focus_minutes_per_break_minute=_integer(
            _required(raw, "focus_minutes_per_break_minute", "focus"),
            "focus.focus_minutes_per_break_minute",
        ),
        minimum_break_minutes=_integer(
            _required(raw, "minimum_break_minutes", "focus"),
            "focus.minimum_break_minutes",
        ),
        grace_active_seconds=_integer(
            _required(raw, "grace_active_seconds", "focus"),
            "focus.grace_active_seconds",
        ),
        happy_seconds=_integer(
            _required(raw, "happy_seconds", "focus"), "focus.happy_seconds"
        ),
        sad_seconds=_integer(
            _required(raw, "sad_seconds", "focus"), "focus.sad_seconds"
        ),
        report_timezone=_string(
            _required(raw, "report_timezone", "focus"), "focus.report_timezone"
        ),
    )


def _feeding(raw: Mapping[str, object]) -> FeedingConfig:
    _exact_keys(raw, {"hunger_seconds", "definitions"}, "feeding")
    definitions_raw = _mapping(
        _required(raw, "definitions", "feeding"), "feeding.definitions"
    )
    definitions: dict[str, FoodDefinition] = {}
    for food_id, value in definitions_raw.items():
        definition = _mapping(value, f"feeding.definitions.{food_id}")
        _exact_keys(
            definition,
            {
                "display_name",
                "sprite_id",
                "price_yarn",
                "happy_seconds",
                "consume_animation",
            },
            f"feeding.definitions.{food_id}",
        )
        definitions[food_id] = FoodDefinition(
            id=food_id,
            sprite_id=_string(
                _required(definition, "sprite_id", f"feeding.definitions.{food_id}"),
                f"feeding.definitions.{food_id}.sprite_id",
            ),
            content_seconds=_integer(
                _required(
                    definition, "happy_seconds", f"feeding.definitions.{food_id}"
                ),
                f"feeding.definitions.{food_id}.happy_seconds",
            ),
            display_name=_string(
                _required(definition, "display_name", f"feeding.definitions.{food_id}"),
                f"feeding.definitions.{food_id}.display_name",
            ),
            price_yarn=_integer(
                _required(definition, "price_yarn", f"feeding.definitions.{food_id}"),
                f"feeding.definitions.{food_id}.price_yarn",
            ),
            consume_animation=_string(
                _required(
                    definition,
                    "consume_animation",
                    f"feeding.definitions.{food_id}",
                ),
                f"feeding.definitions.{food_id}.consume_animation",
            ),
        )
    return FeedingConfig(
        definitions=MappingProxyType(definitions),
        hunger_seconds=_integer(
            _required(raw, "hunger_seconds", "feeding"), "feeding.hunger_seconds"
        ),
    )


def _progression(raw: Mapping[str, object]) -> ProgressionConfig:
    _exact_keys(
        raw,
        {
            "policy_version",
            "starting_yarn",
            "xp_per_level",
            "xp_level_increment",
            "xp_per_focus_minute",
            "yarn_minutes_per_unit",
            "chain_xp_percent",
            "chain_yarn_per_step",
        },
        "progression",
    )
    return ProgressionConfig(
        policy_version=_integer(
            _required(raw, "policy_version", "progression"),
            "progression.policy_version",
        ),
        starting_yarn=_integer(
            _required(raw, "starting_yarn", "progression"),
            "progression.starting_yarn",
        ),
        xp_per_level=_integer(
            _required(raw, "xp_per_level", "progression"),
            "progression.xp_per_level",
        ),
        xp_level_increment=_integer(
            _required(raw, "xp_level_increment", "progression"),
            "progression.xp_level_increment",
        ),
        xp_per_focus_minute=_integer(
            _required(raw, "xp_per_focus_minute", "progression"),
            "progression.xp_per_focus_minute",
        ),
        yarn_minutes_per_unit=_integer(
            _required(raw, "yarn_minutes_per_unit", "progression"),
            "progression.yarn_minutes_per_unit",
        ),
        chain_xp_percent=_integer(
            _required(raw, "chain_xp_percent", "progression"),
            "progression.chain_xp_percent",
        ),
        chain_yarn_per_step=_integer(
            _required(raw, "chain_yarn_per_step", "progression"),
            "progression.chain_yarn_per_step",
        ),
    )


def _activity(raw: Mapping[str, object]) -> ActivityConfig:
    _exact_keys(
        raw,
        {
            "keyboard_one_yarn_keypresses",
            "keyboard_two_yarn_keypresses",
            "camera_minimum_coverage_percent",
            "camera_one_yarn_attention_percent",
            "camera_two_yarn_attention_percent",
        },
        "activity",
    )
    return ActivityConfig(
        keyboard_one_yarn_keypresses=_integer(
            _required(raw, "keyboard_one_yarn_keypresses", "activity"),
            "activity.keyboard_one_yarn_keypresses",
        ),
        keyboard_two_yarn_keypresses=_integer(
            _required(raw, "keyboard_two_yarn_keypresses", "activity"),
            "activity.keyboard_two_yarn_keypresses",
        ),
        camera_minimum_coverage_percent=_integer(
            _required(raw, "camera_minimum_coverage_percent", "activity"),
            "activity.camera_minimum_coverage_percent",
        ),
        camera_one_yarn_attention_percent=_integer(
            _required(raw, "camera_one_yarn_attention_percent", "activity"),
            "activity.camera_one_yarn_attention_percent",
        ),
        camera_two_yarn_attention_percent=_integer(
            _required(raw, "camera_two_yarn_attention_percent", "activity"),
            "activity.camera_two_yarn_attention_percent",
        ),
    )


def _bindings(raw: Mapping[str, object]) -> ControlBindings:
    _exact_keys(raw, {"bindings"}, "controls")
    groups = _mapping(_required(raw, "bindings", "controls"), "controls.bindings")
    bindings: dict[BindingKey, ActionId] = {}
    for context_text, value in groups.items():
        try:
            context = ControlContext(context_text)
        except ValueError as error:
            raise ConfigError(f"unknown control context: {context_text}") from error
        entries = _mapping(value, f"controls.bindings.{context_text}")
        for gesture_key, action_value in entries.items():
            key = _binding_key(context, gesture_key)
            if key in bindings:
                raise ConfigError(
                    f"duplicate control binding: {context_text}.{gesture_key}"
                )
            action_text = _string(
                action_value, f"controls.bindings.{context_text}.{gesture_key}"
            )
            try:
                action_id = ActionId(action_text)
            except ValueError as error:
                raise ConfigError(f"unknown action ID: {action_text}") from error
            if action_id not in ACTIONS:
                raise ConfigError(f"action has no definition: {action_text}")
            bindings[key] = action_id
    missing_contexts = set(ControlContext) - {
        context for context, _button, _gesture in bindings
    }
    if missing_contexts:
        names = ", ".join(sorted(context.value for context in missing_contexts))
        raise ConfigError(f"controls.bindings is missing contexts: {names}")
    return MappingProxyType(bindings)


def _binding_key(context: ControlContext, value: str) -> BindingKey:
    pieces = value.split(".")
    if len(pieces) != 2:
        raise ConfigError(f"binding key must be BUTTON.GESTURE: {value}")
    try:
        button_number = int(pieces[0])
        button = ButtonId(button_number)
        gesture = Gesture(pieces[1])
    except ValueError as error:
        raise ConfigError(f"invalid binding key: {value}") from error
    if button_number <= 0:
        raise ConfigError(f"button ID must be positive: {value}")
    return (context, button, gesture)


def _ui(raw: Mapping[str, object]) -> UiConfig:
    _exact_keys(raw, {"clock_timezone", "max_buttons"}, "ui")
    return UiConfig(
        clock_timezone=_string(
            _required(raw, "clock_timezone", "ui"), "ui.clock_timezone"
        ),
        max_buttons=_integer(_required(raw, "max_buttons", "ui"), "ui.max_buttons"),
    )


def _device(raw: Mapping[str, object]) -> DeviceConfig:
    _exact_keys(raw, {"port", "usb_vid", "usb_pid", "serial_number"}, "device")
    return DeviceConfig(
        port=_optional_string(raw.get("port"), "device.port"),
        usb_vid=_optional_integer(raw.get("usb_vid"), "device.usb_vid"),
        usb_pid=_optional_integer(raw.get("usb_pid"), "device.usb_pid"),
        serial_number=_optional_string(
            raw.get("serial_number"), "device.serial_number"
        ),
    )


def _mapping(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ConfigError(f"{path} must be a mapping with string keys")
    unknown_mapping = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in unknown_mapping):
        raise ConfigError(f"{path} must be a mapping with string keys")
    return cast(dict[str, object], unknown_mapping)


def _list(value: object, path: str) -> list[object]:
    if not isinstance(value, list):
        raise ConfigError(f"{path} must be a list")
    return cast(list[object], value)


def _string(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise ConfigError(f"{path} must be a string")
    return value


def _optional_string(value: object, path: str) -> str | None:
    return None if value is None else _string(value, path)


def _integer(value: object, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigError(f"{path} must be an integer")
    return value


def _optional_integer(value: object, path: str) -> int | None:
    return None if value is None else _integer(value, path)


def _required(raw: Mapping[str, object], key: str, path: str) -> object:
    if key not in raw:
        raise ConfigError(f"{path}.{key} is required")
    return raw[key]


def _exact_keys(raw: Mapping[str, object], expected: set[str], path: str) -> None:
    missing = expected - raw.keys()
    unknown = raw.keys() - expected
    if missing:
        raise ConfigError(f"{path} is missing: {', '.join(sorted(missing))}")
    if unknown:
        raise ConfigError(f"{path} has unknown fields: {', '.join(sorted(unknown))}")
