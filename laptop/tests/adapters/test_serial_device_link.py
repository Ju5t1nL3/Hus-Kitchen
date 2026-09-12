"""Threaded serial lifecycle tests using deterministic fake ports."""

import json
import queue
import threading
import time
import unittest
from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast

from deskpet.adapters.fakes import FakeClock
from deskpet.adapters.serial_device_link import SerialDeviceLink
from deskpet.core.models import ButtonId, ClockReading, Mood, PublishStatus, Screen
from deskpet.core.views import (
    AnimationCue,
    AnimationName,
    ButtonInput,
    ButtonLabel,
    ConnectionChanged,
    DeviceReady,
    InputMessage,
    Pong,
    RenderSnapshot,
)

NOW = ClockReading(datetime(2026, 9, 13, tzinfo=UTC), 1_000, False)
BUTTONS = (ButtonId(1), ButtonId(2))


class FakeSerialPort:
    def __init__(self, *, partial_writes: bool = False) -> None:
        self._reads: queue.Queue[bytes | OSError] = queue.Queue()
        self._lock = threading.Lock()
        self.writes: list[bytes] = []
        self.closed = False
        self.partial_writes = partial_writes

    def push(self, data: bytes) -> None:
        self._reads.put(data)

    def fail(self) -> None:
        self._reads.put(OSError("disconnected"))

    def readline(self) -> bytes:
        if self.closed:
            raise OSError("closed")
        try:
            value = self._reads.get(timeout=0.02)
        except queue.Empty:
            return b""
        if isinstance(value, OSError):
            raise value
        return value

    def write(self, data: bytes, /) -> int:
        if self.closed:
            raise OSError("closed")
        count = max(1, len(data) // 2) if self.partial_writes else len(data)
        with self._lock:
            self.writes.append(data[:count])
        return count

    def close(self) -> None:
        self.closed = True

    def written_bytes(self) -> bytes:
        with self._lock:
            return b"".join(self.writes)


class FakeSerialBackend:
    def __init__(self, *ports: FakeSerialPort, failures: int = 0) -> None:
        self._ports: queue.Queue[FakeSerialPort] = queue.Queue()
        for port in ports:
            self._ports.put(port)
        self.failures = failures
        self.open_count = 0

    def open(self) -> FakeSerialPort:
        self.open_count += 1
        if self.failures:
            self.failures -= 1
            raise OSError("not connected")
        try:
            return self._ports.get_nowait()
        except queue.Empty as error:
            raise OSError("no fake port") from error


def view(clock: str = "14:32") -> RenderSnapshot:
    return RenderSnapshot(
        Screen.HOME,
        1,
        Mood.CALM,
        clock,
        None,
        False,
        None,
        None,
        (
            ButtonLabel(ButtonId(1), "Feed", True),
            ButtonLabel(ButtonId(2), "Focus", True),
        ),
        None,
    )


def message(value: dict[str, object]) -> bytes:
    return (json.dumps(value, separators=(",", ":")) + "\n").encode()


def ready(connection_id: str | None, *, boot: str = "boot-1") -> bytes:
    return message(
        {
            "v": 2,
            "type": "ready",
            "connection_id": connection_id,
            "boot_id": boot,
            "buttons": [1, 2],
            "ui": "emotions_v1",
        }
    )


def wait_for(predicate: Callable[[], bool], message_text: str) -> None:
    deadline = time.monotonic() + 1.5
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError(message_text)


def decoded_writes(port: FakeSerialPort) -> list[dict[str, object]]:
    lines = port.written_bytes().splitlines()
    return [cast(dict[str, object], json.loads(line)) for line in lines]


class SerialDeviceLinkTests(unittest.TestCase):
    def make_link(
        self, backend: FakeSerialBackend, clock: FakeClock | None = None
    ) -> tuple[SerialDeviceLink, list[InputMessage]]:
        received: list[InputMessage] = []
        link = SerialDeviceLink(
            backend,
            clock or FakeClock(NOW),
            connection_id_factory=lambda: "link-1",
        )
        link.start(received.append)
        self.addCleanup(link.stop)
        return link, received

    def handshake(
        self,
        port: FakeSerialPort,
        received: list[InputMessage],
        *,
        connection: str = "link-1",
    ) -> None:
        port.push(ready(None))
        wait_for(
            lambda: any(item.get("type") == "hello" for item in decoded_writes(port)),
            "hello was not written",
        )
        port.push(ready(connection))
        wait_for(
            lambda: any(
                isinstance(item, ConnectionChanged) and item.connected
                for item in received
            ),
            "connection was not established",
        )

    def test_open_retries_then_handshake_and_partial_writes_succeed(self) -> None:
        port = FakeSerialPort(partial_writes=True)
        backend = FakeSerialBackend(port, failures=1)
        _link, received = self.make_link(backend)

        wait_for(lambda: backend.open_count >= 2, "open was not retried")
        self.handshake(port, received)

        writes = decoded_writes(port)
        self.assertEqual(writes[0]["type"], "hello")
        self.assertTrue(any(isinstance(item, DeviceReady) for item in received))

    def test_latest_view_is_restored_after_handshake_and_updates_coalesce(self) -> None:
        port = FakeSerialPort()
        link, received = self.make_link(FakeSerialBackend(port))
        self.assertIs(link.publish(view("14:31"), 1), PublishStatus.DISCONNECTED)
        link.publish(view("14:32"), 2)

        self.handshake(port, received)
        wait_for(
            lambda: any(item.get("type") == "render" for item in decoded_writes(port)),
            "latest render was not restored",
        )

        renders = [
            item for item in decoded_writes(port) if item.get("type") == "render"
        ]
        self.assertEqual(len(renders), 1)
        self.assertEqual(renders[0]["revision"], 2)

    def test_stale_wrong_boot_duplicate_and_undeclared_buttons_are_discarded(
        self,
    ) -> None:
        port = FakeSerialPort()
        _link, received = self.make_link(FakeSerialBackend(port))
        self.handshake(port, received)
        received.clear()
        template: dict[str, object] = {
            "v": 2,
            "type": "button",
            "connection_id": "link-1",
            "boot_id": "boot-1",
            "seq": 1,
            "control_epoch": 1,
            "button": 1,
            "action": "press",
        }
        invalid = (
            {**template, "connection_id": "old"},
            {**template, "boot_id": "old"},
            {**template, "button": 3},
        )
        for value in invalid:
            port.push(message(value))
        port.push(message(template))
        port.push(message(template))

        wait_for(
            lambda: (
                len([item for item in received if isinstance(item, ButtonInput)]) == 1
            ),
            "valid button was not emitted",
        )
        buttons = [item for item in received if isinstance(item, ButtonInput)]
        self.assertEqual([item.seq for item in buttons], [1])

    def test_only_matching_pong_refreshes_liveness_and_timeout_reopens(self) -> None:
        first = FakeSerialPort()
        second = FakeSerialPort()
        clock = FakeClock(NOW)
        backend = FakeSerialBackend(first, second)
        _link, received = self.make_link(backend, clock)
        self.handshake(first, received)
        wait_for(
            lambda: any(item.get("type") == "ping" for item in decoded_writes(first)),
            "ping was not sent",
        )
        first.push(
            message({"v": 2, "type": "pong", "connection_id": "link-1", "nonce": 99})
        )
        time.sleep(0.03)
        self.assertFalse(any(isinstance(item, Pong) for item in received))

        clock.advance(6_001)
        wait_for(
            lambda: any(
                isinstance(item, ConnectionChanged) and not item.connected
                for item in received
            ),
            "heartbeat timeout did not disconnect",
        )
        wait_for(lambda: backend.open_count >= 2, "transport was not reopened")
        self.assertTrue(first.closed)

    def test_reconnect_uses_new_session_and_restores_latest_view(self) -> None:
        first = FakeSerialPort()
        second = FakeSerialPort()
        ids = iter(("link-1", "link-2"))
        backend = FakeSerialBackend(first, second)
        received: list[InputMessage] = []
        link = SerialDeviceLink(
            backend,
            FakeClock(NOW),
            connection_id_factory=lambda: next(ids),
        )
        link.start(received.append)
        self.addCleanup(link.stop)
        self.handshake(first, received)
        link.publish(view(), 5)
        first.fail()
        wait_for(lambda: backend.open_count >= 2, "second port was not opened")
        second.push(ready(None, boot="boot-2"))
        wait_for(
            lambda: any(
                item.get("type") == "hello" and item.get("connection_id") == "link-2"
                for item in decoded_writes(second)
            ),
            "new hello was not sent",
        )
        second.push(ready("link-2", boot="boot-2"))
        wait_for(
            lambda: any(
                item.get("type") == "render" for item in decoded_writes(second)
            ),
            "latest view was not restored after reconnect",
        )

    def test_animation_queue_is_bounded_and_duplicate_cues_drop(self) -> None:
        port = FakeSerialPort()
        link, received = self.make_link(FakeSerialBackend(port))
        self.handshake(port, received)
        cue = AnimationCue("event:feed", AnimationName.FEED, 1, "food_basic")

        self.assertIs(link.animate(cue), PublishStatus.QUEUED)
        self.assertIs(link.animate(cue), PublishStatus.DROPPED)
        for index in range(40):
            link.animate(
                AnimationCue(
                    f"event-{index}:feed",
                    AnimationName.FEED,
                    1,
                    "food_basic",
                )
            )
        time.sleep(0.1)
        animation_count = sum(
            item.get("type") == "animate" for item in decoded_writes(port)
        )
        self.assertLessEqual(animation_count, 33)

    def test_stop_is_idempotent_and_closes_transport(self) -> None:
        port = FakeSerialPort()
        backend = FakeSerialBackend(port)
        link, _received = self.make_link(backend)
        wait_for(lambda: backend.open_count >= 1, "serial port was not opened")

        link.stop()
        link.stop()

        self.assertTrue(port.closed)


if __name__ == "__main__":
    unittest.main()
