"""DeviceLink adapter that drives handshake, heartbeat and connection IDs over a serial port. 
"""

import threading
import uuid
from collections import deque
from dataclasses import dataclass
from typing import Protocol

from deskpet.core.models import PublishStatus
from deskpet.core.ports import InputCallback
from deskpet.core.views import (
    AnimationCue,
    ButtonInput,
    ConnectionChanged,
    DeviceReady,
    Invalid,
    Pong,
    RenderSnapshot,
)
from deskpet.adapters import wire_codec
from deskpet.adapters.wire_codec import (
    AnimateMessage,
    HelloMessage,
    PingMessage,
    RenderMessage,
)

PING_INTERVAL_S = 2.0
PONG_TIMEOUT_S = 6.0
PUMP_INTERVAL_S = 0.05
ANIMATION_QUEUE_SIZE = 32


class ClockProtocol(Protocol):
    def read(self): ...


class SerialPort(Protocol):
    """Matches pyserial.Serial's relevant surface, so fakes need no
    inheritance"""

    def readline(self) -> bytes: ...

    def write(self, data: bytes) -> int: ...

    def close(self) -> None: ...


@dataclass
class _Session:
    connection_id: str
    boot_id: str | None = None
    connected: bool = False
    last_button_seq: int = 0
    next_ping_nonce: int = 1
    last_pong_at_mono_ms: int | None = None
    awaiting_hello_ack: bool = True


class SerialDeviceLink:
    def __init__(self, serial_port: SerialPort, clock: ClockProtocol) -> None:
        self._port = serial_port
        self._clock = clock
        self._on_input: InputCallback | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._session: _Session | None = None
        self._pending_render: RenderMessage | None = None
        self._animation_queue: deque[AnimateMessage] = deque()
        self._recent_animation_ids: deque[str] = deque(maxlen=ANIMATION_QUEUE_SIZE)
        self._reader_thread: threading.Thread | None = None
        self._pump_thread: threading.Thread | None = None

    # ---- DeviceLink protocol ----

    def start(self, on_input: InputCallback) -> None:
        self._on_input = on_input
        self._stop.clear()
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._pump_thread = threading.Thread(target=self._pump_loop, daemon=True)
        self._reader_thread.start()
        self._pump_thread.start()

    def publish(self, view: RenderSnapshot, revision: int) -> PublishStatus:
        with self._lock:
            if self._session is None or not self._session.connected:
                return PublishStatus.DISCONNECTED
            self._pending_render = RenderMessage(
                connection_id=self._session.connection_id, revision=revision, view=view
            )
        return PublishStatus.QUEUED

    def animate(self, cue: AnimationCue) -> PublishStatus:
        with self._lock:
            if self._session is None or not self._session.connected:
                return PublishStatus.DISCONNECTED
            if cue.animation_id in self._recent_animation_ids:
                return PublishStatus.DROPPED
            if len(self._animation_queue) >= ANIMATION_QUEUE_SIZE:
                self._animation_queue.popleft()
            self._animation_queue.append(
                AnimateMessage(connection_id=self._session.connection_id, cue=cue)
            )
            self._recent_animation_ids.append(cue.animation_id)
        return PublishStatus.QUEUED

    def stop(self) -> None:
        self._stop.set()
        if self._reader_thread:
            self._reader_thread.join(timeout=2)
        if self._pump_thread:
            self._pump_thread.join(timeout=2)
        self._port.close()

    # ---- reader thread ----

    def _read_loop(self) -> None:
        while not self._stop.is_set():
            try:
                raw = self._port.readline()
            except OSError:
                self._mark_disconnected()
                return
            if not raw:
                continue

            line = raw.rstrip(b"\r\n")
            if not line:
                continue

            result = wire_codec.decode_line(line, self._clock.read())
            if isinstance(result, Invalid):
                continue
            self._handle_message(result.message)

    def _handle_message(self, message) -> None:
        if isinstance(message, DeviceReady):
            self._handle_ready(message)
        elif isinstance(message, ButtonInput):
            self._handle_button(message)
        elif isinstance(message, Pong):
            self._handle_pong(message)

    def _handle_ready(self, message: DeviceReady) -> None:
        with self._lock:
            if message.connection_id is None:
                connection_id = str(uuid.uuid4())
                self._session = _Session(connection_id=connection_id, boot_id=message.boot_id)
                self._pending_render = None
                self._animation_queue.clear()
                self._recent_animation_ids.clear()
                hello = HelloMessage(connection_id=connection_id)
                self._write(wire_codec.encode(hello))
                return

            session = self._session
            if (
                session is None
                or message.connection_id != session.connection_id
                or message.boot_id != session.boot_id
            ):
                return

            session.awaiting_hello_ack = False
            session.connected = True
            session.last_pong_at_mono_ms = self._clock.read().monotonic_ms

        self._emit(ConnectionChanged(connection_id=message.connection_id, connected=True))
        self._emit(message)

    def _handle_button(self, message: ButtonInput) -> None:
        with self._lock:
            session = self._session
            if (
                session is None
                or not session.connected
                or message.connection_id != session.connection_id
                or message.boot_id != session.boot_id
            ):
                return
            if message.seq <= session.last_button_seq:
                return
            session.last_button_seq = message.seq
        self._emit(message)

    def _handle_pong(self, message: Pong) -> None:
        with self._lock:
            session = self._session
            if session is None or message.connection_id != session.connection_id:
                return
            session.last_pong_at_mono_ms = self._clock.read().monotonic_ms
        self._emit(message)

    # ---- pump thread: heartbeat + outbound flush ----

    def _pump_loop(self) -> None:
        last_ping_at_mono_ms: int | None = None

        while not self._stop.is_set():
            now = self._clock.read()

            with self._lock:
                session = self._session
                if session is not None and session.connected:
                    if session.last_pong_at_mono_ms is not None and (
                        now.monotonic_ms - session.last_pong_at_mono_ms
                        > PONG_TIMEOUT_S * 1000
                    ):
                        session.connected = False
                        connection_id = session.connection_id
                        self._session = None
                        self._pending_render = None
                        self._animation_queue.clear()
                        should_notify_disconnect = True
                    else:
                        should_notify_disconnect = False
                else:
                    should_notify_disconnect = False

                should_ping = (
                    session is not None
                    and session.connected
                    and (
                        last_ping_at_mono_ms is None
                        or now.monotonic_ms - last_ping_at_mono_ms >= PING_INTERVAL_S * 1000
                    )
                )
                if should_ping:
                    nonce = session.next_ping_nonce
                    session.next_ping_nonce += 1
                    ping = PingMessage(connection_id=session.connection_id, nonce=nonce)
                else:
                    ping = None

                render = self._pending_render
                self._pending_render = None
                cue = self._animation_queue.popleft() if self._animation_queue else None

            if should_notify_disconnect:
                self._emit(ConnectionChanged(connection_id=connection_id, connected=False))
            if ping is not None:
                last_ping_at_mono_ms = now.monotonic_ms
                self._write(wire_codec.encode(ping))
            if render is not None:
                self._write(wire_codec.encode(render))
            if cue is not None:
                self._write(wire_codec.encode(cue))

            self._stop.wait(PUMP_INTERVAL_S)

    # ---- helpers ----

    def _write(self, data: bytes) -> None:
        try:
            self._port.write(data)
        except OSError:
            self._mark_disconnected()

    def _mark_disconnected(self) -> None:
        with self._lock:
            session = self._session
            if session is None or not session.connected:
                return
            session.connected = False
            connection_id = session.connection_id
            self._session = None
        self._emit(ConnectionChanged(connection_id=connection_id, connected=False))

    def _emit(self, message) -> None:
        if self._on_input is not None:
            self._on_input(message)
