"""Laptop <-> Pico wire codec (protocol v2).

Owns wire fields and bounds per docs/serial_protocol.md: pure shape/type/
range/enum validation only. Connection ID matching, sequence/epoch checks
and heartbeat bookkeeping belong to SerialDeviceLink, not here.
"""

import json
import re
from dataclasses import dataclass
from typing import TypeIs, cast

from deskpet.core.models import ButtonId, ClockReading, Gesture, Screen
from deskpet.core.views import (
    AnimationCue,
    ButtonInput,
    ButtonLabel,
    DeviceReady,
    EarnedRewardsView,
    Invalid,
    Parsed,
    ParseResult,
    Pong,
    ProgressionView,
    RenderSnapshot,
    SettingsView,
)

PROTOCOL_VERSION = 2
UI_VOCABULARY = "emotions_v1"
MAX_LINE_BYTES = 2048

_GESTURES = {g.value: g for g in Gesture}
_ANIMATION_NAMES = {"feed", "celebrate"}
_CLOCK_PATTERN = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d")


class EncodeError(ValueError):
    """Raised when asked to encode an invalid or oversized host message."""


@dataclass(frozen=True, slots=True)
class HelloMessage:
    connection_id: str


@dataclass(frozen=True, slots=True)
class PingMessage:
    connection_id: str
    nonce: int


@dataclass(frozen=True, slots=True)
class RenderMessage:
    connection_id: str
    revision: int
    view: RenderSnapshot


@dataclass(frozen=True, slots=True)
class AnimateMessage:
    connection_id: str
    cue: AnimationCue


HostMessage = HelloMessage | PingMessage | RenderMessage | AnimateMessage
type JsonValue = (
    None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
)
type JsonObject = dict[str, JsonValue]


class LineDecoder:
    """Incrementally frame arbitrary serial chunks into validated messages."""

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._discarding_oversized = False

    def feed(self, chunk: bytes, now: ClockReading) -> tuple[ParseResult, ...]:
        results: list[ParseResult] = []
        for byte in chunk:
            if self._discarding_oversized:
                if byte == 0x0A:
                    self._discarding_oversized = False
                    results.append(Invalid("line_too_long"))
                continue

            self._buffer.append(byte)
            if byte == 0x0A:
                framed = bytes(self._buffer)
                self._buffer.clear()
                if len(framed) > MAX_LINE_BYTES:
                    results.append(Invalid("line_too_long"))
                    continue
                line = framed[:-1]
                if line.endswith(b"\r"):
                    line = line[:-1]
                results.append(decode_line(line, now))
            elif len(self._buffer) >= MAX_LINE_BYTES:
                self._buffer.clear()
                self._discarding_oversized = True
        return tuple(results)

    def reset(self) -> None:
        self._buffer.clear()
        self._discarding_oversized = False


def decode_line(
    raw: bytes,
    now: ClockReading,
    declared_buttons: tuple[ButtonId, ...] | None = None,
) -> ParseResult:
    """Decode one already-assembled, newline-stripped line.

    `now` is an explicit clock sample attached to a resulting ButtonInput --
    this stays pure (no implicit clock read, no I/O), it just cannot invent
    a receipt time for a wire message that carries none.
    """
    if len(raw) + 1 > MAX_LINE_BYTES:
        return Invalid("line_too_long")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return Invalid("bad_utf8")

    try:
        decoded: object = json.loads(text)
    except ValueError:
        return Invalid("bad_json")

    if not isinstance(decoded, dict):
        return Invalid("not_object")
    message = cast(dict[str, object], decoded)
    if message.get("v") != PROTOCOL_VERSION:
        return Invalid("bad_version")

    msg_type = message.get("type")
    if msg_type == "ready":
        return _decode_ready(message)
    if msg_type == "button":
        result = _decode_button(message, now)
        if (
            declared_buttons is not None
            and isinstance(result, Parsed)
            and isinstance(result.message, ButtonInput)
            and result.message.button not in declared_buttons
        ):
            return Invalid("undeclared_button")
        return result
    if msg_type == "pong":
        return _decode_pong(message)
    return Invalid("unknown_type")


def _decode_ready(message: dict[str, object]) -> ParseResult:
    connection_id = message.get("connection_id")
    if connection_id is not None and not _valid_id(connection_id):
        return Invalid("bad_connection_id")

    boot_id = message.get("boot_id")
    if not _valid_id(boot_id):
        return Invalid("bad_boot_id")

    buttons = message.get("buttons")
    if not _valid_button_list(buttons):
        return Invalid("bad_buttons")

    if message.get("ui") != UI_VOCABULARY:
        return Invalid("bad_ui")

    return Parsed(
        DeviceReady(
            connection_id=connection_id,
            boot_id=boot_id,
            buttons=tuple(ButtonId(b) for b in buttons),
            ui=UI_VOCABULARY,
        )
    )


def _decode_button(message: dict[str, object], now: ClockReading) -> ParseResult:
    connection_id = message.get("connection_id")
    boot_id = message.get("boot_id")
    if not _valid_id(connection_id) or not _valid_id(boot_id):
        return Invalid("bad_ids")

    seq = message.get("seq")
    if not _is_positive_int(seq):
        return Invalid("bad_seq")

    control_epoch = message.get("control_epoch")
    if not _is_positive_int(control_epoch):
        return Invalid("bad_control_epoch")

    button = message.get("button")
    if not _is_int(button) or not (1 <= button <= 255):
        return Invalid("bad_button")

    action = message.get("action")
    if not isinstance(action, str) or action not in _GESTURES:
        return Invalid("bad_action")

    return Parsed(
        ButtonInput(
            connection_id=connection_id,
            boot_id=boot_id,
            seq=seq,
            control_epoch=control_epoch,
            button=ButtonId(button),
            action=_GESTURES[action],
            received_at=now,
        )
    )


def _decode_pong(message: dict[str, object]) -> ParseResult:
    connection_id = message.get("connection_id")
    if not _valid_id(connection_id):
        return Invalid("bad_connection_id")

    nonce = message.get("nonce")
    if not _is_int(nonce) or nonce < 0:
        return Invalid("bad_nonce")

    return Parsed(Pong(connection_id=connection_id, nonce=nonce))


def encode(
    message: HostMessage,
    declared_buttons: tuple[ButtonId, ...] | None = None,
) -> bytes:
    if isinstance(message, HelloMessage):
        payload = _encode_hello(message)
    elif isinstance(message, PingMessage):
        payload = _encode_ping(message)
    elif isinstance(message, RenderMessage):
        payload = _encode_render(message, declared_buttons)
    else:
        payload = _encode_animate(message)

    encoded = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
    if len(encoded) > MAX_LINE_BYTES:
        raise EncodeError("encoded message exceeds MAX_LINE_BYTES")
    return encoded


def _encode_hello(message: HelloMessage) -> JsonObject:
    if not _valid_id(message.connection_id):
        raise EncodeError("invalid connection_id")
    return {
        "v": PROTOCOL_VERSION,
        "type": "hello",
        "connection_id": message.connection_id,
    }


def _encode_ping(message: PingMessage) -> JsonObject:
    if not _valid_id(message.connection_id):
        raise EncodeError("invalid connection_id")
    if not _is_int(message.nonce) or message.nonce < 0:
        raise EncodeError("nonce must be nonnegative")
    return {
        "v": PROTOCOL_VERSION,
        "type": "ping",
        "connection_id": message.connection_id,
        "nonce": message.nonce,
    }


def _encode_render(
    message: RenderMessage,
    declared_buttons: tuple[ButtonId, ...] | None,
) -> JsonObject:
    if not _valid_id(message.connection_id):
        raise EncodeError("invalid connection_id")
    if not _is_positive_int(message.revision):
        raise EncodeError("revision must be positive")

    view = message.view
    _validate_view(view, declared_buttons)

    buttons: list[JsonValue] = [_encode_button_label(label) for label in view.buttons]
    encoded_view: JsonObject = {
        "screen": view.screen.value,
        "control_epoch": view.control_epoch,
        "mood": view.mood.value,
        "clock_text": view.clock_text,
        "timer_seconds": view.timer_seconds,
        "paused": view.paused,
        "focus_minutes": view.focus_minutes,
        "break_minutes": view.break_minutes,
        "buttons": buttons,
        "feedback": view.feedback.value if view.feedback is not None else None,
        "progression": _encode_progression(view.progression),
        "earned_rewards": _encode_rewards(view.earned_rewards),
    }
    if view.settings is not None:
        encoded_view["settings"] = _encode_settings(view.settings)
    return {
        "v": PROTOCOL_VERSION,
        "type": "render",
        "connection_id": message.connection_id,
        "revision": message.revision,
        "view": encoded_view,
    }


def _encode_button_label(label: ButtonLabel) -> JsonObject:
    if not _printable_ascii(label.label, 12):
        raise EncodeError("invalid button label")
    if not _is_int(label.button) or not 1 <= label.button <= 255:
        raise EncodeError("invalid button ID")
    return {"button": int(label.button), "label": label.label, "enabled": label.enabled}


def _encode_progression(value: ProgressionView | None) -> JsonObject | None:
    if value is None:
        return None
    return {
        "level": value.level,
        "xp_into_level": value.xp_into_level,
        "xp_for_next_level": value.xp_for_next_level,
        "yarn_balance": value.yarn_balance,
    }


def _encode_rewards(value: EarnedRewardsView | None) -> JsonObject | None:
    if value is None:
        return None
    return {"xp": value.xp, "yarn": value.yarn}


def _encode_settings(value: SettingsView | None) -> JsonObject | None:
    if value is None:
        return None
    return {
        "selected_row": value.selected_row,
        "keyboard_enabled": value.keyboard_enabled,
        "keyboard_available": value.keyboard_available,
        "camera_enabled": value.camera_enabled,
        "camera_available": value.camera_available,
    }


def _encode_animate(message: AnimateMessage) -> JsonObject:
    if not _valid_id(message.connection_id):
        raise EncodeError("invalid connection_id")

    cue = message.cue
    name = cue.name.value
    if name not in _ANIMATION_NAMES:
        raise EncodeError("invalid animation name")
    if not _is_positive_int(cue.after_revision):
        raise EncodeError("after_revision must be positive")
    if not _printable_ascii(cue.animation_id, 96):
        raise EncodeError("invalid animation_id length")
    if name == "feed" and (
        cue.food_sprite is None or not _printable_ascii(cue.food_sprite, 64)
    ):
        raise EncodeError("feed animation requires a valid item sprite")
    if name == "celebrate" and cue.food_sprite is not None:
        raise EncodeError("celebrate animation cannot include food_sprite")

    return {
        "v": PROTOCOL_VERSION,
        "type": "animate",
        "connection_id": message.connection_id,
        "animation_id": cue.animation_id,
        "after_revision": cue.after_revision,
        "name": name,
        "food_sprite": cue.food_sprite,
    }


def _valid_id(value: object) -> TypeIs[str]:
    return isinstance(value, str) and _printable_ascii(value, 64)


def _printable_ascii(value: str, maximum: int) -> bool:
    return 1 <= len(value) <= maximum and all(
        0x20 <= ord(char) <= 0x7E for char in value
    )


def _validate_view(
    view: RenderSnapshot, declared_buttons: tuple[ButtonId, ...] | None
) -> None:
    if not _is_positive_int(view.control_epoch):
        raise EncodeError("control_epoch must be positive")
    is_timer = view.screen in {Screen.FOCUS, Screen.BREAK}
    revealing_clock = view.screen is Screen.FOCUS and view.clock_text is not None
    if view.screen is Screen.HOME:
        if view.clock_text is None or _CLOCK_PATTERN.fullmatch(view.clock_text) is None:
            raise EncodeError("home requires a valid clock_text")
        if view.progression is None:
            raise EncodeError("home requires progression")
    elif revealing_clock:
        if _CLOCK_PATTERN.fullmatch(view.clock_text or "") is None:
            raise EncodeError("focus clock reveal requires a valid clock_text")
    elif view.clock_text is not None:
        raise EncodeError("clock_text is only valid on home")
    if view.screen is Screen.FEED and view.progression is None:
        raise EncodeError("feed menu requires progression")
    if view.screen not in {Screen.HOME, Screen.FEED} and view.progression is not None:
        raise EncodeError("progression is only valid on home or feed")
    if view.screen is not Screen.BREAK_OFFER and view.earned_rewards is not None:
        raise EncodeError("earned_rewards is only valid on break_offer")
    if (view.screen is Screen.SETTINGS) != (view.settings is not None):
        raise EncodeError("settings data is required only on settings")
    if is_timer:
        if revealing_clock and view.timer_seconds is not None:
            raise EncodeError("focus clock reveal cannot include timer_seconds")
        if not revealing_clock and (
            not _is_int(view.timer_seconds) or not 0 <= view.timer_seconds <= 3_600
        ):
            raise EncodeError("timer screen requires valid timer_seconds")
    elif view.timer_seconds is not None or view.paused:
        raise EncodeError("non-timer screen cannot have timer state")
    if view.screen is Screen.SETUP:
        if (
            not _is_int(view.focus_minutes)
            or not 5 <= view.focus_minutes <= 60
            or view.focus_minutes % 5 != 0
        ):
            raise EncodeError("setup requires valid focus_minutes")
    elif view.focus_minutes is not None:
        raise EncodeError("focus_minutes is only valid on setup")
    if view.screen in {Screen.SETUP, Screen.BREAK_OFFER}:
        if not _is_int(view.break_minutes) or not 1 <= view.break_minutes <= 60:
            raise EncodeError("screen requires valid break_minutes")
    elif view.break_minutes is not None:
        raise EncodeError("break_minutes is invalid on this screen")

    ids = tuple(label.button for label in view.buttons)
    if not 1 <= len(ids) <= 8 or len(set(ids)) != len(ids):
        raise EncodeError("view buttons must contain 1-8 unique IDs")
    if declared_buttons is not None and ids != declared_buttons:
        raise EncodeError("view buttons do not match advertised order")


def _is_int(value: object) -> TypeIs[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_positive_int(value: object) -> TypeIs[int]:
    return _is_int(value) and value > 0


def _valid_button_list(buttons: object) -> TypeIs[list[int]]:
    if not isinstance(buttons, list):
        return False
    values = cast(list[object], buttons)
    if not 1 <= len(values) <= 8:
        return False
    if not all(_is_int(button) and 1 <= button <= 255 for button in values):
        return False
    return len(set(cast(list[int], values))) == len(values)
