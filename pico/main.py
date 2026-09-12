"""Cooperative firmware loop: USB protocol, buttons and rendering.

This is the whole of the Pico's decision-making: assemble/validate USB
input, track connection/revision/epoch state, scan buttons and hand the
laptop-selected view to the renderer. It must never decide timer outcomes,
emotions, rewards or persistence -- see ../docs/system_design.md and
../docs/serial_protocol.md.

Not yet smoke-tested on-device (M17); in particular whether the desk-pet
protocol can share the USB CDC stream cleanly with the REPL still needs
on-board confirmation (see ../pico/README.md).
"""

import os
import select
import sys
import time

import machine
import micropython
from buttons import ButtonScanner
from display import NullDisplayDriver, Renderer
from hardware_config import BUTTONS, DEBOUNCE_MS, HOLD_MS
from protocol import Protocol

_HEARTBEAT_TIMEOUT_MS = 6000

_poll = select.poll()
_poll.register(sys.stdin, select.POLLIN)


def _make_boot_id():
    board_id = machine.unique_id().hex()
    boot_nonce = os.urandom(4).hex()
    return "boot-" + board_id + "-" + boot_nonce


def _read_available():
    chunk = b""
    while _poll.poll(0):
        byte = sys.stdin.buffer.read(1)
        if not byte:
            break
        chunk += byte
    return chunk


def _write(data):
    sys.stdout.buffer.write(data)


class FirmwareApp:
    """Poll USB/buttons, flush bounded output, update display."""

    def __init__(self, protocol, scanner, renderer):
        self._protocol = protocol
        self._scanner = scanner
        self._renderer = renderer
        self._seq = 0

    def feed_serial(self, chunk):
        if not chunk:
            return
        for message in self._protocol.feed(chunk):
            self._dispatch(message)

    def _dispatch(self, message):
        action = self._protocol.accept(message, time.ticks_ms())
        if action is None:
            return
        kind = action["kind"]
        if kind == "reset_connection":
            self._scanner.reset_until_release()
            self._seq = 0
            self._renderer.set_connected(True)
            _write(self._protocol.encode_ready())
        elif kind == "pong":
            _write(self._protocol.encode_pong(action["nonce"]))
        elif kind == "set_view":
            self._renderer.set_view(action["view"])
        elif kind == "enqueue_animation":
            self._renderer.enqueue_animation(
                action["animation_id"], action["name"], action["food_sprite"]
            )

    def step(self, now_ms):
        if self._protocol.connected and self._protocol.is_timed_out(
            now_ms, _HEARTBEAT_TIMEOUT_MS
        ):
            self._protocol.connected = False
            self._protocol.has_valid_view = False
            self._renderer.set_connected(False)

        gestures = self._scanner.poll(now_ms, self._protocol.control_epoch)
        if self._protocol.connected and self._protocol.has_valid_view:
            for gesture in gestures:
                self._seq += 1
                _write(
                    self._protocol.encode_button(
                        self._seq,
                        gesture["control_epoch"],
                        gesture["button"],
                        gesture["action"],
                    )
                )

        self._renderer.tick(now_ms)


def main():
    # The desk-pet protocol owns this USB stream once running; a stray
    # Ctrl-C byte in a JSON line must not raise KeyboardInterrupt.
    micropython.kbd_intr(-1)

    protocol = Protocol(_make_boot_id(), tuple(button["id"] for button in BUTTONS))
    scanner = ButtonScanner(BUTTONS, DEBOUNCE_MS, HOLD_MS)
    renderer = Renderer(NullDisplayDriver())
    app = FirmwareApp(protocol, scanner, renderer)

    _write(protocol.encode_ready())

    while True:
        app.feed_serial(_read_available())
        app.step(time.ticks_ms())


if __name__ == "__main__":
    main()
