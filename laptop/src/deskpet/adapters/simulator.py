"""In-memory serial transport and protocol-validating virtual Pico."""

import json
import queue
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol, cast

from deskpet.adapters import wire_codec
from deskpet.adapters.wire_codec import (
    AnimateMessage,
    HelloMessage,
    PingMessage,
    RenderMessage,
)
from deskpet.core.models import (
    ButtonId,
    ClockReading,
    Feedback,
    Gesture,
    Mood,
    PublishStatus,
    Screen,
)
from deskpet.core.ports import Clock, DeviceLink, InputCallback
from deskpet.core.views import (
    AnimationCue,
    AnimationName,
    ButtonInput,
    ButtonLabel,
    DeviceReady,
    EarnedRewardsView,
    Parsed,
    Pong,
    ProgressionView,
    RenderSnapshot,
    SettingsView,
    Shutdown,
    Tick,
)

TRACE_LIMIT = 250
DEFAULT_BUTTONS = (ButtonId(1), ButtonId(2), ButtonId(3))


class TraceDirection(StrEnum):
    DEVICE_TO_LAPTOP = "device_to_laptop"
    LAPTOP_TO_DEVICE = "laptop_to_device"


@dataclass(frozen=True, slots=True)
class TraceEntry:
    sequence: int
    timestamp: str
    direction: TraceDirection
    raw: str
    message_type: str | None
    accepted: bool
    result: str


class TraceSink:
    """Thread-safe bounded diagnostic history; never a gameplay event store."""

    def __init__(self, limit: int = TRACE_LIMIT) -> None:
        if limit <= 0:
            raise ValueError("trace limit must be positive")
        self._entries: deque[TraceEntry] = deque(maxlen=limit)
        self._lock = threading.Lock()
        self._sequence = 0
        self._paused = False

    def record(
        self,
        direction: TraceDirection,
        raw: bytes,
        message_type: str | None,
        accepted: bool,
        result: str,
    ) -> None:
        with self._lock:
            if self._paused:
                return
            self._sequence += 1
            self._entries.append(
                TraceEntry(
                    sequence=self._sequence,
                    timestamp=datetime.now(UTC).isoformat(),
                    direction=direction,
                    raw=raw.decode("utf-8", errors="replace").rstrip("\r\n"),
                    message_type=message_type,
                    accepted=accepted,
                    result=result,
                )
            )

    def snapshot(self) -> tuple[TraceEntry, ...]:
        with self._lock:
            return tuple(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def set_paused(self, paused: bool) -> None:
        with self._lock:
            self._paused = paused

    @property
    def paused(self) -> bool:
        with self._lock:
            return self._paused


class ControllableClock(Clock):
    """Real-running paired clock with an explicit development-only offset."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._offset_ms = 0
        self._origin_mono_ms = time.monotonic_ns() // 1_000_000
        self._origin_utc = datetime.now(UTC)

    def read(self) -> ClockReading:
        with self._lock:
            elapsed_ms = time.monotonic_ns() // 1_000_000 - self._origin_mono_ms
            logical_ms = elapsed_ms + self._offset_ms
            return ClockReading(
                utc=self._origin_utc + timedelta(milliseconds=logical_ms),
                monotonic_ms=self._origin_mono_ms + logical_ms,
                resumed=False,
            )

    def advance(self, milliseconds: int) -> ClockReading:
        if milliseconds < 0:
            raise ValueError("milliseconds must be nonnegative")
        with self._lock:
            self._offset_ms += milliseconds
        return self.read()


class _DeviceWriter(Protocol):
    def push_from_device(self, data: bytes) -> None: ...


class _LifecycleServer(Protocol):
    def start(self) -> None: ...

    def stop(self) -> None: ...


class VirtualPico:
    """Minimal Pico protocol peer whose state is safe to expose to the dev UI."""

    def __init__(
        self,
        clock: Clock,
        trace: TraceSink,
        buttons: tuple[ButtonId, ...] = DEFAULT_BUTTONS,
    ) -> None:
        self._clock = clock
        self._trace = trace
        self._buttons = buttons
        self._lock = threading.RLock()
        self._writer: _DeviceWriter | None = None
        self._boot_number = 1
        self._boot_id = "sim-boot-1"
        self._connection_id: str | None = None
        self._button_seq = 0
        self._revision = 0
        self._view: RenderSnapshot | None = None
        self._last_animation: AnimationCue | None = None
        self._host_buffer = bytearray()
        self._discarding = False

    def attach(self, writer: _DeviceWriter) -> None:
        with self._lock:
            self._writer = writer
            self._connection_id = None
            self._button_seq = 0
            self._revision = 0
            self._view = None
            self._last_animation = None
            self._send_ready()

    def detach(self, writer: _DeviceWriter) -> None:
        with self._lock:
            if self._writer is writer:
                self._writer = None

    def reboot(self) -> None:
        with self._lock:
            self._boot_number += 1
            self._boot_id = f"sim-boot-{self._boot_number}"
            self._connection_id = None
            self._button_seq = 0
            self._revision = 0
            self._view = None
            self._last_animation = None
            self._host_buffer.clear()
            self._discarding = False
            if self._writer is not None:
                self._send_ready()

    def accept_host_bytes(self, chunk: bytes) -> None:
        """Frame and validate bytes written by the production laptop link."""
        with self._lock:
            for byte in chunk:
                if self._discarding:
                    if byte == 0x0A:
                        self._discarding = False
                        self._trace.record(
                            TraceDirection.LAPTOP_TO_DEVICE,
                            b"<oversized line>",
                            None,
                            False,
                            "line_too_long",
                        )
                    continue
                self._host_buffer.append(byte)
                if byte == 0x0A:
                    line = bytes(self._host_buffer)
                    self._host_buffer.clear()
                    self._accept_host_line(line)
                elif len(self._host_buffer) >= wire_codec.MAX_LINE_BYTES:
                    self._host_buffer.clear()
                    self._discarding = True

    def press(self, button: ButtonId, gesture: Gesture) -> bool:
        with self._lock:
            if (
                self._writer is None
                or self._connection_id is None
                or self._view is None
                or button not in self._buttons
            ):
                return False
            self._button_seq += 1
            payload: dict[str, object] = {
                "v": wire_codec.PROTOCOL_VERSION,
                "type": "button",
                "connection_id": self._connection_id,
                "boot_id": self._boot_id,
                "seq": self._button_seq,
                "control_epoch": self._view.control_epoch,
                "button": int(button),
                "action": gesture.value,
            }
            self._send_device_json(payload)
            return True

    def inject_device_line(self, raw: bytes) -> None:
        with self._lock:
            if self._writer is None:
                return
            data = raw if raw.endswith(b"\n") else raw + b"\n"
            result = wire_codec.decode_line(
                data.rstrip(b"\r\n"), self._clock.read(), self._buttons
            )
            if isinstance(result, Parsed):
                message_type = _device_message_type(result.message)
                accepted, detail = self._device_acceptance(result.message)
            else:
                message_type = None
                accepted = False
                detail = result.code
            self._trace.record(
                TraceDirection.DEVICE_TO_LAPTOP,
                data,
                message_type,
                accepted,
                detail,
            )
            self._writer.push_from_device(data)

    def _device_acceptance(
        self, message: DeviceReady | ButtonInput | Pong
    ) -> tuple[bool, str]:
        if isinstance(message, ButtonInput):
            if message.connection_id != self._connection_id:
                return False, "wrong_connection"
            if message.boot_id != self._boot_id:
                return False, "wrong_boot"
            if self._view is None:
                return False, "no_current_view"
            if message.control_epoch != self._view.control_epoch:
                return False, "stale_control_epoch"
        return True, "decoded"

    def public_state(self, connected: bool) -> dict[str, object]:
        with self._lock:
            view = self._view
            return {
                "connected": connected and self._writer is not None,
                "boot_id": self._boot_id,
                "connection_id": self._connection_id,
                "buttons": [int(button) for button in self._buttons],
                "revision": self._revision,
                "view": _view_json(view) if view is not None else None,
                "last_animation": (
                    {
                        "name": self._last_animation.name.value,
                        "animation_id": self._last_animation.animation_id,
                    }
                    if self._last_animation is not None
                    else None
                ),
            }

    def _accept_host_line(self, raw: bytes) -> None:
        stripped = raw.rstrip(b"\r\n")
        message_type: str | None = None
        try:
            decoded = json.loads(stripped.decode("utf-8"))
            if not isinstance(decoded, dict):
                raise ValueError("not_object")
            payload = cast(dict[str, object], decoded)
            raw_type = payload.get("type")
            message_type = raw_type if isinstance(raw_type, str) else None
            self._accept_host_payload(payload)
        except (UnicodeDecodeError, ValueError, KeyError, TypeError) as error:
            result = str(error) or "invalid_message"
            self._trace.record(
                TraceDirection.LAPTOP_TO_DEVICE,
                raw,
                message_type,
                False,
                result,
            )
            return
        self._trace.record(
            TraceDirection.LAPTOP_TO_DEVICE,
            raw,
            message_type,
            True,
            "accepted",
        )

    def _accept_host_payload(self, payload: dict[str, object]) -> None:
        if payload.get("v") != wire_codec.PROTOCOL_VERSION:
            raise ValueError("bad_version")
        message_type = payload.get("type")
        if message_type == "hello":
            connection_id = _required_str(payload, "connection_id")
            wire_codec.encode(HelloMessage(connection_id))
            self._connection_id = connection_id
            self._button_seq = 0
            self._revision = 0
            self._view = None
            self._last_animation = None
            self._send_ready()
            return
        if message_type == "ping":
            connection_id = _required_str(payload, "connection_id")
            nonce = _required_int(payload, "nonce")
            wire_codec.encode(PingMessage(connection_id, nonce))
            self._require_connection(connection_id)
            self._send_device_json(
                {
                    "v": wire_codec.PROTOCOL_VERSION,
                    "type": "pong",
                    "connection_id": connection_id,
                    "nonce": nonce,
                }
            )
            return
        if message_type == "render":
            connection_id = _required_str(payload, "connection_id")
            self._require_connection(connection_id)
            revision = _required_int(payload, "revision")
            if revision <= self._revision:
                raise ValueError("stale_revision")
            view_value = payload.get("view")
            if not isinstance(view_value, dict):
                raise ValueError("bad_view")
            view = _decode_view(cast(dict[str, object], view_value))
            wire_codec.encode(
                RenderMessage(connection_id, revision, view), self._buttons
            )
            if self._view is not None and view.control_epoch < self._view.control_epoch:
                raise ValueError("decreasing_control_epoch")
            self._revision = revision
            self._view = view
            return
        if message_type == "animate":
            connection_id = _required_str(payload, "connection_id")
            self._require_connection(connection_id)
            cue = AnimationCue(
                animation_id=_required_str(payload, "animation_id"),
                name=AnimationName(_required_str(payload, "name")),
                after_revision=_required_int(payload, "after_revision"),
                food_sprite=_optional_str(payload, "food_sprite"),
            )
            wire_codec.encode(AnimateMessage(connection_id, cue))
            if cue.after_revision > self._revision:
                raise ValueError("animation_before_render")
            self._last_animation = cue
            return
        raise ValueError("unknown_type")

    def _require_connection(self, connection_id: str) -> None:
        if connection_id != self._connection_id:
            raise ValueError("wrong_connection")

    def _send_ready(self) -> None:
        self._send_device_json(
            {
                "v": wire_codec.PROTOCOL_VERSION,
                "type": "ready",
                "connection_id": self._connection_id,
                "boot_id": self._boot_id,
                "buttons": [int(button) for button in self._buttons],
                "ui": wire_codec.UI_VOCABULARY,
            }
        )

    def _send_device_json(self, payload: dict[str, object]) -> None:
        data = (json.dumps(payload, separators=(",", ":")) + "\n").encode()
        self.inject_device_line(data)


class SimulatorPort:
    """One open in-memory serial connection."""

    def __init__(self, pico: VirtualPico) -> None:
        self._pico = pico
        self._reads: queue.Queue[bytes | None] = queue.Queue()
        self._closed = False
        self._lock = threading.Lock()

    def open(self) -> None:
        self._pico.attach(self)

    def readline(self) -> bytes:
        try:
            value = self._reads.get(timeout=0.05)
        except queue.Empty:
            return b""
        if value is None:
            raise OSError("simulator disconnected")
        return value

    def write(self, data: bytes, /) -> int:
        with self._lock:
            if self._closed:
                raise OSError("simulator port is closed")
        self._pico.accept_host_bytes(data)
        return len(data)

    def push_from_device(self, data: bytes) -> None:
        with self._lock:
            if self._closed:
                return
        self._reads.put(data)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._pico.detach(self)
        while True:
            try:
                self._reads.get_nowait()
            except queue.Empty:
                break
        self._reads.put(None)

    def disconnect(self) -> None:
        self.close()


class SimulatorBackend:
    """Reconnectable backend controlled explicitly by the development UI."""

    def __init__(self, pico: VirtualPico) -> None:
        self._pico = pico
        self._lock = threading.Lock()
        self._enabled = True
        self._port: SimulatorPort | None = None

    @property
    def connected(self) -> bool:
        with self._lock:
            return self._enabled and self._port is not None

    def open(self) -> SimulatorPort:
        with self._lock:
            if not self._enabled:
                raise OSError("virtual Pico is disconnected")
            port = SimulatorPort(self._pico)
            self._port = port
        port.open()
        return port

    def connect(self) -> None:
        with self._lock:
            self._enabled = True

    def disconnect(self) -> None:
        with self._lock:
            self._enabled = False
            port = self._port
            self._port = None
        if port is not None:
            port.disconnect()


class SimulatorDeviceLink(DeviceLink):
    """DeviceLink facade plus controls consumed only by the development server."""

    def __init__(
        self,
        link: DeviceLink,
        backend: SimulatorBackend,
        pico: VirtualPico,
        clock: ControllableClock,
        trace: TraceSink,
    ) -> None:
        self._link = link
        self._backend = backend
        self._pico = pico
        self._clock = clock
        self._trace = trace
        self._on_input: InputCallback | None = None
        self._server: _LifecycleServer | None = None

    def attach_server(self, server: _LifecycleServer) -> None:
        if self._server is not None:
            raise RuntimeError("simulator server is already attached")
        self._server = server

    def start(self, on_input: InputCallback) -> None:
        self._on_input = on_input
        if self._server is not None:
            self._server.start()
        try:
            self._link.start(on_input)
        except BaseException:
            if self._server is not None:
                self._server.stop()
            raise

    def publish(self, view: RenderSnapshot, revision: int) -> PublishStatus:
        return self._link.publish(view, revision)

    def animate(self, cue: AnimationCue) -> PublishStatus:
        return self._link.animate(cue)

    def stop(self) -> None:
        try:
            self._link.stop()
        finally:
            if self._server is not None:
                self._server.stop()
            self._on_input = None

    def connect(self) -> None:
        self._backend.connect()

    def disconnect(self) -> None:
        self._backend.disconnect()

    def reboot(self) -> None:
        self._pico.reboot()

    def press(self, button: int, gesture: str) -> bool:
        return self._pico.press(ButtonId(button), Gesture(gesture))

    def advance(self, seconds: int) -> ClockReading:
        if seconds < 0 or seconds > 3_600:
            raise ValueError("advance seconds must be between 0 and 3600")
        reading = self._clock.advance(seconds * 1_000)
        callback = self._on_input
        if callback is not None:
            callback(Tick(reading))
        return reading

    def inject(self, raw: str) -> None:
        self._pico.inject_device_line(raw.encode())

    def request_shutdown(self) -> None:
        callback = self._on_input
        if callback is not None:
            callback(Shutdown())

    def state(self) -> dict[str, object]:
        return {
            **self._pico.public_state(self._backend.connected),
            "clock": self._clock.read().utc.isoformat(),
            "trace_paused": self._trace.paused,
            "trace": [
                {**asdict(entry), "direction": entry.direction.value}
                for entry in self._trace.snapshot()
            ],
        }

    def clear_trace(self) -> None:
        self._trace.clear()

    def pause_trace(self, paused: bool) -> None:
        self._trace.set_paused(paused)


def _decode_view(value: dict[str, object]) -> RenderSnapshot:
    buttons_value = value.get("buttons")
    if not isinstance(buttons_value, list):
        raise ValueError("bad_buttons")
    labels: list[ButtonLabel] = []
    for raw_label in cast(list[object], buttons_value):
        if not isinstance(raw_label, dict):
            raise ValueError("bad_button_label")
        label = cast(dict[str, object], raw_label)
        enabled = label.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("bad_button_enabled")
        labels.append(
            ButtonLabel(
                ButtonId(_required_int(label, "button")),
                _required_str(label, "label"),
                enabled,
            )
        )
    paused = value.get("paused")
    if not isinstance(paused, bool):
        raise ValueError("bad_paused")
    feedback_value = value.get("feedback")
    feedback = None if feedback_value is None else Feedback(str(feedback_value))
    progression_value = value.get("progression")
    progression = None
    if progression_value is not None:
        if not isinstance(progression_value, dict):
            raise ValueError("bad_progression")
        raw_progression = cast(dict[str, object], progression_value)
        progression = ProgressionView(
            level=_required_int(raw_progression, "level"),
            xp_into_level=_required_int(raw_progression, "xp_into_level"),
            xp_for_next_level=_required_int(raw_progression, "xp_for_next_level"),
            yarn_balance=_required_int(raw_progression, "yarn_balance"),
        )
    rewards_value = value.get("earned_rewards")
    rewards = None
    if rewards_value is not None:
        if not isinstance(rewards_value, dict):
            raise ValueError("bad_earned_rewards")
        raw_rewards = cast(dict[str, object], rewards_value)
        rewards = EarnedRewardsView(
            xp=_required_int(raw_rewards, "xp"),
            yarn=_required_int(raw_rewards, "yarn"),
        )
    settings_value = value.get("settings")
    settings = None
    if settings_value is not None:
        if not isinstance(settings_value, dict):
            raise ValueError("bad_settings")
        raw_settings = cast(dict[str, object], settings_value)
        keyboard_enabled = raw_settings.get("keyboard_enabled")
        keyboard_available = raw_settings.get("keyboard_available")
        camera_enabled = raw_settings.get("camera_enabled")
        camera_available = raw_settings.get("camera_available")
        if not all(
            isinstance(item, bool)
            for item in (
                keyboard_enabled,
                keyboard_available,
                camera_enabled,
                camera_available,
            )
        ):
            raise ValueError("bad_settings_flags")
        settings = SettingsView(
            selected_row=_required_int(raw_settings, "selected_row"),
            keyboard_enabled=bool(keyboard_enabled),
            keyboard_available=bool(keyboard_available),
            camera_enabled=bool(camera_enabled),
            camera_available=bool(camera_available),
        )
    return RenderSnapshot(
        screen=Screen(_required_str(value, "screen")),
        control_epoch=_required_int(value, "control_epoch"),
        mood=Mood(_required_str(value, "mood")),
        clock_text=_optional_str(value, "clock_text"),
        timer_seconds=_optional_int(value, "timer_seconds"),
        paused=paused,
        focus_minutes=_optional_int(value, "focus_minutes"),
        break_minutes=_optional_int(value, "break_minutes"),
        buttons=tuple(labels),
        feedback=feedback,
        progression=progression,
        earned_rewards=rewards,
        settings=settings,
    )


def _device_message_type(message: DeviceReady | ButtonInput | Pong) -> str:
    if isinstance(message, DeviceReady):
        return "ready"
    if isinstance(message, ButtonInput):
        return "button"
    return "pong"


def _view_json(view: RenderSnapshot) -> dict[str, object]:
    return {
        "screen": view.screen.value,
        "control_epoch": view.control_epoch,
        "mood": view.mood.value,
        "clock_text": view.clock_text,
        "timer_seconds": view.timer_seconds,
        "paused": view.paused,
        "focus_minutes": view.focus_minutes,
        "break_minutes": view.break_minutes,
        "buttons": [
            {"button": int(item.button), "label": item.label, "enabled": item.enabled}
            for item in view.buttons
        ],
        "feedback": view.feedback.value if view.feedback else None,
        "progression": None
        if view.progression is None
        else {
            "level": view.progression.level,
            "xp_into_level": view.progression.xp_into_level,
            "xp_for_next_level": view.progression.xp_for_next_level,
            "yarn_balance": view.progression.yarn_balance,
        },
        "earned_rewards": None
        if view.earned_rewards is None
        else {"xp": view.earned_rewards.xp, "yarn": view.earned_rewards.yarn},
        "settings": None
        if view.settings is None
        else {
            "selected_row": view.settings.selected_row,
            "keyboard_enabled": view.settings.keyboard_enabled,
            "keyboard_available": view.settings.keyboard_available,
            "camera_enabled": view.settings.camera_enabled,
            "camera_available": view.settings.camera_available,
        },
    }


def _required_str(value: dict[str, object], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str):
        raise ValueError(f"bad_{key}")
    return result


def _optional_str(value: dict[str, object], key: str) -> str | None:
    result = value.get(key)
    if result is not None and not isinstance(result, str):
        raise ValueError(f"bad_{key}")
    return result


def _required_int(value: dict[str, object], key: str) -> int:
    result = value.get(key)
    if not isinstance(result, int) or isinstance(result, bool):
        raise ValueError(f"bad_{key}")
    return result


def _optional_int(value: dict[str, object], key: str) -> int | None:
    result = value.get(key)
    if result is not None and (not isinstance(result, int) or isinstance(result, bool)):
        raise ValueError(f"bad_{key}")
    return result
