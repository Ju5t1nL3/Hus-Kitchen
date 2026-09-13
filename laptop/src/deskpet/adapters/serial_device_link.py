"""Threaded, reconnecting DeviceLink over an injected serial backend."""

import threading
import uuid
from collections import deque
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass

from deskpet.adapters import wire_codec
from deskpet.adapters.serial_discovery import SerialBackend, SerialPort
from deskpet.adapters.wire_codec import (
    AnimateMessage,
    HelloMessage,
    PingMessage,
    RenderMessage,
)
from deskpet.core.models import ButtonId, PublishStatus
from deskpet.core.ports import Clock, InputCallback
from deskpet.core.views import (
    AnimationCue,
    ButtonInput,
    ConnectionChanged,
    DeviceMessage,
    DeviceReady,
    InputMessage,
    Invalid,
    Pong,
    RenderSnapshot,
)

PING_INTERVAL_MS = 2_000
PONG_TIMEOUT_MS = 6_000
PUMP_INTERVAL_SECONDS = 0.05
RECONNECT_INTERVAL_SECONDS = 0.25
ANIMATION_QUEUE_SIZE = 32


@dataclass(slots=True)
class _Session:
    connection_id: str
    boot_id: str
    buttons: tuple[ButtonId, ...]
    connected: bool = False
    last_button_seq: int = 0
    next_ping_nonce: int = 1
    awaiting_ping_nonce: int | None = None
    last_pong_at_mono_ms: int | None = None


class SerialDeviceLink:
    """Own serial workers and session validation, never gameplay decisions."""

    def __init__(
        self,
        backend: SerialBackend,
        clock: Clock,
        *,
        connection_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._backend = backend
        self._clock = clock
        self._connection_id_factory = connection_id_factory or (
            lambda: str(uuid.uuid4())
        )
        self._on_input: InputCallback | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._port: SerialPort | None = None
        self._session: _Session | None = None
        # A connection_id we proactively picked and said hello with right after
        # opening the port, awaiting the device's first matching reply -- see
        # _current_or_open_port(). Covers a real device that already sent its
        # one-shot boot-time `ready(connection_id=null)` announce before this
        # process's port was even open to receive it, which would otherwise
        # deadlock: the device only re-announces in reply to a hello, and this
        # process would only send one in reply to that announce.
        self._pending_connection_id: str | None = None
        self._latest_view: tuple[RenderSnapshot, int] | None = None
        self._pending_render: RenderMessage | None = None
        self._animation_queue: deque[AnimateMessage] = deque()
        self._recent_animation_ids: deque[str] = deque(maxlen=ANIMATION_QUEUE_SIZE)
        self._reader_thread: threading.Thread | None = None
        self._pump_thread: threading.Thread | None = None
        self._line_decoder = wire_codec.LineDecoder()

    def start(self, on_input: InputCallback) -> None:
        """Start reader/pump workers; opening failures retry in the background."""
        with self._lock:
            if self._reader_thread is not None and self._reader_thread.is_alive():
                raise RuntimeError("device link is already started")
            self._on_input = on_input
            self._stop.clear()
            self._line_decoder.reset()
            self._pending_connection_id = None
            self._recent_animation_ids.clear()
            self._reader_thread = threading.Thread(
                target=self._read_loop, name="deskpet-serial-reader", daemon=True
            )
            self._pump_thread = threading.Thread(
                target=self._pump_loop, name="deskpet-serial-pump", daemon=True
            )
            reader = self._reader_thread
            pump = self._pump_thread
        reader.start()
        pump.start()

    def publish(self, view: RenderSnapshot, revision: int) -> PublishStatus:
        """Retain the latest view and coalesce any older unsent snapshot."""
        with self._lock:
            self._latest_view = (view, revision)
            session = self._session
            if session is None or not session.connected:
                return PublishStatus.DISCONNECTED
            if tuple(label.button for label in view.buttons) != session.buttons:
                return PublishStatus.DROPPED
            self._pending_render = RenderMessage(session.connection_id, revision, view)
            return PublishStatus.QUEUED

    def animate(self, cue: AnimationCue) -> PublishStatus:
        """Queue a best-effort cue once, dropping the oldest under pressure."""
        with self._lock:
            session = self._session
            if session is None or not session.connected:
                return PublishStatus.DISCONNECTED
            if cue.animation_id in self._recent_animation_ids:
                return PublishStatus.DROPPED
            if len(self._animation_queue) >= ANIMATION_QUEUE_SIZE:
                self._animation_queue.popleft()
            self._animation_queue.append(AnimateMessage(session.connection_id, cue))
            self._recent_animation_ids.append(cue.animation_id)
            return PublishStatus.QUEUED

    def stop(self) -> None:
        """Stop idempotently and close first so a blocking read can wake."""
        self._stop.set()
        self._close_transport(notify=True)
        reader = self._reader_thread
        pump = self._pump_thread
        if reader is not None and reader is not threading.current_thread():
            reader.join(timeout=2)
        if pump is not None and pump is not threading.current_thread():
            pump.join(timeout=2)
        with self._lock:
            self._reader_thread = None
            self._pump_thread = None
            self._on_input = None

    def _read_loop(self) -> None:
        while not self._stop.is_set():
            port = self._current_or_open_port()
            if port is None:
                self._stop.wait(RECONNECT_INTERVAL_SECONDS)
                continue
            try:
                raw = port.readline()
            except OSError:
                self._transport_failed(port)
                continue
            if not raw:
                continue
            for result in self._line_decoder.feed(raw, self._clock.read()):
                if not isinstance(result, Invalid):
                    self._handle_message(result.message)

    def _current_or_open_port(self) -> SerialPort | None:
        with self._lock:
            current = self._port
        if current is not None:
            return current
        try:
            opened = self._backend.open()
        except OSError:
            return None
        connection_id = self._connection_id_factory()
        with self._lock:
            if self._stop.is_set() or self._port is not None:
                keep = False
            else:
                self._port = opened
                self._line_decoder.reset()
                self._pending_connection_id = connection_id
                keep = True
        if not keep:
            opened.close()
            return None
        # Say hello immediately rather than only in reply to the device's
        # boot-time announce -- that announce is sent once and may already be
        # gone by the time this port is open to receive it. A real device
        # replies to any hello the same way regardless of what prompted it.
        self._write(wire_codec.encode(HelloMessage(connection_id)))
        return opened

    def _handle_message(self, message: DeviceMessage) -> None:
        if isinstance(message, DeviceReady):
            self._handle_ready(message)
        elif isinstance(message, ButtonInput):
            self._handle_button(message)
        else:
            self._handle_pong(message)

    def _handle_ready(self, message: DeviceReady) -> None:
        if message.connection_id is None:
            disconnected_id: str | None = None
            with self._lock:
                # Reuse a hello already sent proactively on port-open rather
                # than picking a second id and sending a redundant one -- this
                # announce may just be the boot-time original arriving after
                # (rather than instead of) that proactive hello.
                connection_id = self._pending_connection_id or self._connection_id_factory()
                old = self._session
                if old is not None and old.connected:
                    disconnected_id = old.connection_id
                self._session = _Session(
                    connection_id=connection_id,
                    boot_id=message.boot_id,
                    buttons=message.buttons,
                )
                self._pending_connection_id = None
                self._pending_render = None
                self._animation_queue.clear()
            if disconnected_id is not None:
                self._emit(ConnectionChanged(disconnected_id, False))
            self._write(wire_codec.encode(HelloMessage(connection_id)))
            return

        with self._lock:
            session = self._session
            if session is None or message.connection_id != session.connection_id:
                if message.connection_id != self._pending_connection_id:
                    return
                # First reply to a hello this process sent proactively right
                # after opening the port, without ever seeing the device's
                # boot-time announce -- this reply is the first place we learn
                # its boot_id and advertised buttons.
                self._pending_connection_id = None
                session = _Session(
                    connection_id=message.connection_id,
                    boot_id=message.boot_id,
                    buttons=message.buttons,
                )
                self._session = session
            elif message.boot_id != session.boot_id or message.buttons != session.buttons:
                return
            first_ack = not session.connected
            session.connected = True
            session.last_pong_at_mono_ms = self._clock.read().monotonic_ms
            if self._latest_view is not None:
                view, revision = self._latest_view
                if tuple(label.button for label in view.buttons) == session.buttons:
                    self._pending_render = RenderMessage(
                        session.connection_id, revision, view
                    )
        if first_ack:
            self._emit(ConnectionChanged(message.connection_id, True))
            self._emit(message)

    def _handle_button(self, message: ButtonInput) -> None:
        with self._lock:
            session = self._session
            if (
                session is None
                or not session.connected
                or message.connection_id != session.connection_id
                or message.boot_id != session.boot_id
                or message.button not in session.buttons
                or message.seq <= session.last_button_seq
            ):
                return
            session.last_button_seq = message.seq
        self._emit(message)

    def _handle_pong(self, message: Pong) -> None:
        with self._lock:
            session = self._session
            if (
                session is None
                or not session.connected
                or message.connection_id != session.connection_id
                or message.nonce != session.awaiting_ping_nonce
            ):
                return
            session.awaiting_ping_nonce = None
            session.last_pong_at_mono_ms = self._clock.read().monotonic_ms
        self._emit(message)

    def _pump_loop(self) -> None:
        last_ping_at_mono_ms: int | None = None
        while not self._stop.wait(PUMP_INTERVAL_SECONDS):
            now = self._clock.read()
            timeout_port: SerialPort | None = None
            ping: PingMessage | None = None
            render: RenderMessage | None = None
            cue: AnimateMessage | None = None
            declared_buttons: tuple[ButtonId, ...] | None = None
            with self._lock:
                session = self._session
                if (
                    session is not None
                    and session.connected
                    and session.last_pong_at_mono_ms is not None
                    and now.monotonic_ms - session.last_pong_at_mono_ms
                    > PONG_TIMEOUT_MS
                ):
                    timeout_port = self._port
                elif session is not None and session.connected:
                    declared_buttons = session.buttons
                    if (
                        last_ping_at_mono_ms is None
                        or now.monotonic_ms - last_ping_at_mono_ms >= PING_INTERVAL_MS
                    ):
                        nonce = session.next_ping_nonce
                        session.next_ping_nonce += 1
                        session.awaiting_ping_nonce = nonce
                        ping = PingMessage(session.connection_id, nonce)
                        last_ping_at_mono_ms = now.monotonic_ms
                    render = self._pending_render
                    self._pending_render = None
                    if self._animation_queue:
                        cue = self._animation_queue.popleft()

            if timeout_port is not None:
                self._transport_failed(timeout_port)
                last_ping_at_mono_ms = None
                continue
            if ping is not None:
                self._write(wire_codec.encode(ping))
            if render is not None:
                self._write(wire_codec.encode(render, declared_buttons))
            if cue is not None:
                self._write(wire_codec.encode(cue))

    def _write(self, data: bytes) -> None:
        # The reader sends handshake replies while the pump sends views and
        # heartbeats. Keep each encoded line atomic across those two workers.
        with self._write_lock:
            with self._lock:
                port = self._port
            if port is None:
                return
            written = 0
            try:
                while written < len(data):
                    count = port.write(data[written:])
                    if count is None or count <= 0:
                        raise OSError("serial write made no progress")
                    written += count
            except OSError:
                self._transport_failed(port)

    def _transport_failed(self, failed_port: SerialPort) -> None:
        with self._lock:
            if self._port is not failed_port:
                return
        self._close_transport(notify=True)

    def _close_transport(self, *, notify: bool) -> None:
        with self._lock:
            port = self._port
            self._port = None
            session = self._session
            self._session = None
            self._pending_connection_id = None
            self._pending_render = None
            self._animation_queue.clear()
        if port is not None:
            with suppress(OSError):
                port.close()
        if notify and session is not None and session.connected:
            self._emit(ConnectionChanged(session.connection_id, False))

    def _emit(self, message: InputMessage) -> None:
        callback = self._on_input
        if callback is not None:
            callback(message)
