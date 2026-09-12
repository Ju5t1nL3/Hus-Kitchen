"""Laptop <-> Pico wire codec (protocol v2).

Owns wire fields and bounds per docs/serial_protocol.md: pure shape/type/
range/enum validation only. Connection ID matching, sequence/epoch checks
and heartbeat bookkeeping belong to SerialDeviceLink, not here.
"""

import json
from dataclasses import dataclass
from typing import TypeIs, cast

from deskpet.core.models import ButtonId, ClockReading, Gesture, Mood, Screen
from deskpet.core.views import (
    AnimationCue,
    ButtonInput,
    ButtonLabel,
    DeviceReady,
    Invalid,
    Parsed,
    ParseResult,
    Pong,
    RenderSnapshot,
)

PROTOCOL_VERSION = 2
UI_VOCABULARY = "emotions_v1"
MAX_LINE_BYTES = 2048

_GESTURES = {g.value: g for g in Gesture}
_SCREENS = {s.value: s for s in Screen}
_MOODS = {m.value: m for m in Mood}
_FEEDBACKS = {"unavailable", "storage_error"}
_ANIMATION_NAMES = {"feed", "celebrate"}


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


def decode_line(raw: bytes, now: ClockReading) -> ParseResult:
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
        return _decode_button(message, now)
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


def encode(message: HostMessage) -> bytes:
    if isinstance(message, HelloMessage):
        payload = _encode_hello(message)
    elif isinstance(message, PingMessage):
        payload = _encode_ping(message)
    elif isinstance(message, RenderMessage):
        payload = _encode_render(message)
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
    if message.nonce < 0:
        raise EncodeError("nonce must be nonnegative")
    return {
        "v": PROTOCOL_VERSION,
        "type": "ping",
        "connection_id": message.connection_id,
        "nonce": message.nonce,
    }


def _encode_render(message: RenderMessage) -> JsonObject:
    if not _valid_id(message.connection_id):
        raise EncodeError("invalid connection_id")
    if message.revision <= 0:
        raise EncodeError("revision must be positive")

    view = message.view
    if view.screen not in _SCREENS.values():
        raise EncodeError("invalid screen")
    if view.mood not in _MOODS.values():
        raise EncodeError("invalid mood")
    if view.feedback is not None and view.feedback not in _FEEDBACKS:
        raise EncodeError("invalid feedback")

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
    }
    return {
        "v": PROTOCOL_VERSION,
        "type": "render",
        "connection_id": message.connection_id,
        "revision": message.revision,
        "view": encoded_view,
    }


def _encode_button_label(label: ButtonLabel) -> JsonObject:
    if not (1 <= len(label.label) <= 12) or not label.label.isprintable():
        raise EncodeError("invalid button label")
    return {"button": int(label.button), "label": label.label, "enabled": label.enabled}


def _encode_animate(message: AnimateMessage) -> JsonObject:
    if not _valid_id(message.connection_id):
        raise EncodeError("invalid connection_id")

    cue = message.cue
    name = cue.name.value
    if name not in _ANIMATION_NAMES:
        raise EncodeError("invalid animation name")
    if cue.after_revision <= 0:
        raise EncodeError("after_revision must be positive")
    if not (1 <= len(cue.animation_id) <= 96):
        raise EncodeError("invalid animation_id length")

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
    return isinstance(value, str) and 1 <= len(value) <= 64 and value.isprintable()


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
