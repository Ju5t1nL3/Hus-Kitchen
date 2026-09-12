"""Wire protocol v2: line assembly, validation, connection state and encoding.

Mirrors ../docs/serial_protocol.md exactly. Firmware validates shape and
connection/revision/epoch bookkeeping only; it never assigns game meaning to
a message. `feed()` is pure parsing/validation; `accept()` is the only place
that touches connection state, so it is the single source of truth for
`connection_id`, the last accepted revision and `control_epoch`.
"""

import json
import time

PROTOCOL_VERSION = 2
UI_ID = "emotions_v1"
MAX_LINE_BYTES = 2048

_SCREENS = ("home", "setup", "focus", "break_offer", "break")
_MOODS = ("calm", "content", "happy", "sad", "focused", "resting")
_FEEDBACK_VALUES = (None, "unavailable", "storage_error")
_ANIMATION_NAMES = ("feed", "celebrate")


def _is_printable_ascii(value, min_len, max_len):
    if not isinstance(value, str) or not (min_len <= len(value) <= max_len):
        return False
    return all(32 <= ord(ch) <= 126 for ch in value)


def _is_plain_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_plain_bool(value):
    return isinstance(value, bool)


def _is_clock_text(value):
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
        return False
    hh, mm = value[:2], value[3:]
    if not (hh.isdigit() and mm.isdigit()):
        return False
    return 0 <= int(hh) <= 23 and 0 <= int(mm) <= 59


def _validate_view(view, advertised_buttons):
    if not isinstance(view, dict):
        return False
    if view.get("screen") not in _SCREENS:
        return False
    epoch = view.get("control_epoch")
    if not _is_plain_int(epoch) or epoch <= 0:
        return False
    if view.get("mood") not in _MOODS:
        return False

    clock_text = view.get("clock_text")
    if clock_text is not None and not _is_clock_text(clock_text):
        return False

    timer_seconds = view.get("timer_seconds")
    if timer_seconds is not None and not (
        _is_plain_int(timer_seconds) and 0 <= timer_seconds <= 3600
    ):
        return False

    if not _is_plain_bool(view.get("paused")):
        return False

    focus_minutes = view.get("focus_minutes")
    if focus_minutes is not None and not (
        _is_plain_int(focus_minutes)
        and 5 <= focus_minutes <= 60
        and focus_minutes % 5 == 0
    ):
        return False

    break_minutes = view.get("break_minutes")
    if break_minutes is not None and not (
        _is_plain_int(break_minutes) and 1 <= break_minutes <= 60
    ):
        return False

    if view.get("feedback") not in _FEEDBACK_VALUES:
        return False

    return _validate_buttons(view.get("buttons"), advertised_buttons)


def _validate_buttons(buttons, advertised_buttons):
    if not isinstance(buttons, list) or len(buttons) != len(advertised_buttons):
        return False
    for expected_id, entry in zip(advertised_buttons, buttons):
        if not isinstance(entry, dict) or entry.get("button") != expected_id:
            return False
        if not _is_printable_ascii(entry.get("label"), 1, 12):
            return False
        if not _is_plain_bool(entry.get("enabled")):
            return False
    return True


class Protocol:
    """Parses/validates the wire protocol and tracks per-connection state."""

    def __init__(self, boot_id, advertised_buttons):
        self._boot_id = boot_id
        self._advertised = tuple(advertised_buttons)
        self._buffer = bytearray()
        self._discarding = False
        self._last_revision = 0
        self._last_traffic_ms = None

        self.connection_id = None
        self.control_epoch = 0
        self.connected = False
        self.has_valid_view = False

    def feed(self, chunk):
        """Available bytes -> bounded nonblocking line assembly and validation."""
        messages = []
        self._buffer.extend(chunk)
        while True:
            idx = self._buffer.find(b"\n")
            if idx == -1:
                if len(self._buffer) >= MAX_LINE_BYTES:
                    self._buffer = bytearray()
                    self._discarding = True
                break
            oversized = (idx + 1) > MAX_LINE_BYTES
            line = bytes(self._buffer[:idx])
            del self._buffer[: idx + 1]
            if self._discarding or oversized:
                self._discarding = False
                continue
            if line.endswith(b"\r"):
                line = line[:-1]
            message = self._parse_line(line)
            if message is not None:
                messages.append(message)
        return messages

    def _parse_line(self, line):
        try:
            message = json.loads(line.decode("utf-8"))
        except (UnicodeError, ValueError):
            return None
        if not isinstance(message, dict) or message.get("v") != PROTOCOL_VERSION:
            return None

        msg_type = message.get("type")
        if msg_type == "hello":
            return self._parse_hello(message)
        if msg_type == "ping":
            return self._parse_ping(message)
        if msg_type == "render":
            return self._parse_render(message)
        if msg_type == "animate":
            return self._parse_animate(message)
        return None

    def _parse_hello(self, message):
        connection_id = message.get("connection_id")
        if not _is_printable_ascii(connection_id, 1, 64):
            return None
        return {"type": "hello", "connection_id": connection_id}

    def _parse_ping(self, message):
        connection_id = message.get("connection_id")
        if not _is_printable_ascii(connection_id, 1, 64):
            return None
        nonce = message.get("nonce")
        if not _is_plain_int(nonce) or nonce < 0:
            return None
        return {"type": "ping", "connection_id": connection_id, "nonce": nonce}

    def _parse_render(self, message):
        connection_id = message.get("connection_id")
        if not _is_printable_ascii(connection_id, 1, 64):
            return None
        revision = message.get("revision")
        if not _is_plain_int(revision) or revision <= 0:
            return None
        view = message.get("view")
        if not _validate_view(view, self._advertised):
            return None
        return {
            "type": "render",
            "connection_id": connection_id,
            "revision": revision,
            "view": view,
        }

    def _parse_animate(self, message):
        connection_id = message.get("connection_id")
        if not _is_printable_ascii(connection_id, 1, 64):
            return None
        animation_id = message.get("animation_id")
        if not _is_printable_ascii(animation_id, 1, 96):
            return None
        after_revision = message.get("after_revision")
        if not _is_plain_int(after_revision) or after_revision <= 0:
            return None
        name = message.get("name")
        if name not in _ANIMATION_NAMES:
            return None
        food_sprite = message.get("food_sprite")
        if name == "feed" and food_sprite != "food_basic":
            return None
        if name == "celebrate" and food_sprite is not None:
            return None
        return {
            "type": "animate",
            "connection_id": connection_id,
            "animation_id": animation_id,
            "after_revision": after_revision,
            "name": name,
            "food_sprite": food_sprite,
        }

    def accept(self, message, now_ms):
        """Parsed message/time -> DeviceAction or None.

        Applies connection/revision/epoch validation on top of the shape
        validation already done by `feed()`.
        """
        if message["type"] == "hello":
            self.connection_id = message["connection_id"]
            self._last_revision = 0
            self.control_epoch = 0
            self.connected = True
            self.has_valid_view = False
            self._last_traffic_ms = now_ms
            return {"kind": "reset_connection"}

        if message["connection_id"] != self.connection_id:
            return None
        self._last_traffic_ms = now_ms

        if message["type"] == "ping":
            return {"kind": "pong", "nonce": message["nonce"]}

        if message["type"] == "render":
            if message["revision"] <= self._last_revision:
                return None
            epoch = message["view"]["control_epoch"]
            if epoch < self.control_epoch:
                return None
            self._last_revision = message["revision"]
            self.control_epoch = epoch
            self.has_valid_view = True
            return {
                "kind": "set_view",
                "view": message["view"],
                "revision": message["revision"],
            }

        if message["type"] == "animate":
            if message["after_revision"] > self._last_revision:
                return None
            return {
                "kind": "enqueue_animation",
                "animation_id": message["animation_id"],
                "name": message["name"],
                "food_sprite": message["food_sprite"],
            }

        return None

    def is_timed_out(self, now_ms, timeout_ms=6000):
        if self._last_traffic_ms is None:
            return False
        return time.ticks_diff(now_ms, self._last_traffic_ms) >= timeout_ms

    def encode_ready(self):
        return _encode(
            {
                "v": PROTOCOL_VERSION,
                "type": "ready",
                "connection_id": self.connection_id,
                "boot_id": self._boot_id,
                "buttons": list(self._advertised),
                "ui": UI_ID,
            }
        )

    def encode_button(self, seq, control_epoch, button, action):
        return _encode(
            {
                "v": PROTOCOL_VERSION,
                "type": "button",
                "connection_id": self.connection_id,
                "boot_id": self._boot_id,
                "seq": seq,
                "control_epoch": control_epoch,
                "button": button,
                "action": action,
            }
        )

    def encode_pong(self, nonce):
        return _encode(
            {
                "v": PROTOCOL_VERSION,
                "type": "pong",
                "connection_id": self.connection_id,
                "nonce": nonce,
            }
        )


def _encode(payload):
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
