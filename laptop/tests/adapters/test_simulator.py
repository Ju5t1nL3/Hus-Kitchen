"""End-to-end development simulator tests over the production JSON link."""

import threading
import time
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import cast
from unittest.mock import patch

from deskpet.adapters.config_loader import load
from deskpet.adapters.fakes import FakeEventStore
from deskpet.adapters.serial_device_link import SerialDeviceLink
from deskpet.adapters.simulator import (
    ControllableClock,
    SimulatorBackend,
    SimulatorDeviceLink,
    TraceDirection,
    TraceSink,
    VirtualPico,
)
from deskpet.adapters.simulator_web import SIMULATOR_HTML, SimulatorWebServer
from deskpet.adapters.system_clock import SystemClock
from deskpet.app.application import Application
from deskpet.core.models import Screen

CONFIG_PATH = Path(__file__).parents[2] / "config.yaml"


def wait_for(predicate: Callable[[], bool], message: str) -> None:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError(message)


class SimulatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = ControllableClock()
        self.trace = TraceSink()
        self.pico = VirtualPico(self.clock, self.trace)
        self.backend = SimulatorBackend(self.pico)
        connection_ids = iter(("sim-link-1", "sim-link-2", "sim-link-3"))
        self.device = SimulatorDeviceLink(
            SerialDeviceLink(
                self.backend,
                SystemClock(),
                connection_id_factory=lambda: next(connection_ids),
            ),
            self.backend,
            self.pico,
            self.clock,
            self.trace,
        )
        self.store = FakeEventStore()
        self.app = Application(
            self.store,
            self.device,
            self.clock,
            load(CONFIG_PATH),
        )
        self.app.start()
        self.run_thread = threading.Thread(target=self.app.run, daemon=True)
        self.run_thread.start()
        wait_for(lambda: self._screen() is Screen.HOME, "home view was not rendered")

    def tearDown(self) -> None:
        self.device.request_shutdown()
        self.run_thread.join(timeout=2)
        self.app.stop()

    def _state(self) -> dict[str, object]:
        return self.device.state()

    def _screen(self) -> Screen | None:
        view = self._state()["view"]
        if not isinstance(view, dict):
            return None
        screen = cast_view_value(cast(dict[object, object], view)).get("screen")
        return Screen(screen) if isinstance(screen, str) else None

    def _press(self, button: int, expected: Screen) -> None:
        self.assertTrue(self.device.press(button, "press"))
        wait_for(lambda: self._screen() is expected, f"did not reach {expected.value}")

    def test_full_focus_pause_resume_and_break_flow_uses_json_both_ways(self) -> None:
        self._press(2, Screen.SETUP)
        self.assertTrue(self.device.press(1, "press"))
        wait_for(
            lambda: cast_view(self._state()).get("focus_minutes") == 30,
            "duration did not cycle",
        )
        self._press(2, Screen.FOCUS)

        self.assertTrue(self.device.press(1, "press"))
        wait_for(
            lambda: cast_view(self._state()).get("clock_text") is not None,
            "real-time reveal was not encoded",
        )

        self.device.advance(5)
        wait_for(
            lambda: cast_view(self._state()).get("timer_seconds") is not None,
            "countdown did not return after the reveal",
        )
        self.device.advance(5)
        self.assertTrue(self.device.press(2, "press"))
        wait_for(
            lambda: cast_view(self._state()).get("paused") is True,
            "focus did not pause",
        )
        paused_seconds = cast_view(self._state())["timer_seconds"]
        self.device.advance(90)
        wait_for(
            lambda: cast_view(self._state())["timer_seconds"] == paused_seconds,
            "paused time changed",
        )
        self.assertTrue(self.device.press(2, "press"))
        wait_for(
            lambda: cast_view(self._state()).get("paused") is False,
            "focus did not resume",
        )

        self.device.advance(30 * 60)
        wait_for(
            lambda: self._screen() is Screen.BREAK_OFFER,
            "focus did not complete",
        )
        self._press(1, Screen.BREAK)
        self.device.advance(6 * 60)
        wait_for(lambda: self._screen() is Screen.HOME, "break did not complete")

        entries = self.trace.snapshot()
        directions = {entry.direction for entry in entries}
        self.assertEqual(
            directions,
            {TraceDirection.DEVICE_TO_LAPTOP, TraceDirection.LAPTOP_TO_DEVICE},
        )
        self.assertTrue(any(entry.message_type == "button" for entry in entries))
        self.assertTrue(any(entry.message_type == "render" for entry in entries))
        self.assertTrue(all('": ' not in entry.raw for entry in entries))

    def test_settings_hold_and_toggle_traverse_production_codec(self) -> None:
        self.assertTrue(self.device.press(1, "hold"))
        wait_for(lambda: self._screen() is Screen.SETTINGS, "settings did not open")
        settings = cast_view(self._state()).get("settings")
        self.assertIsInstance(settings, dict)
        assert isinstance(settings, dict)
        self.assertFalse(settings["keyboard_enabled"])
        self.assertFalse(settings["camera_available"])

        self.assertTrue(self.device.press(2, "press"))
        wait_for(
            lambda: bool(
                cast(dict[str, object], cast_view(self._state()).get("settings"))[
                    "keyboard_enabled"
                ]
            ),
            "keyboard setting did not toggle",
        )
        settings = cast_view(self._state()).get("settings")
        assert isinstance(settings, dict)
        self.assertTrue(settings["keyboard_enabled"])

    def test_feed_menu_purchase_traverses_production_json_codec(self) -> None:
        self.device.advance(300)
        self._press(1, Screen.FEED)
        view = cast_view(self._state())
        buttons = cast(list[dict[str, object]], view["buttons"])
        self.assertEqual(
            [button["label"] for button in buttons],
            ["Jollof 3Y", "Coffee 2Y", "Back"],
        )

        self._press(2, Screen.HOME)

        progression = cast(dict[str, object], cast_view(self._state())["progression"])
        self.assertEqual(progression["yarn_balance"], 8)
        self.assertTrue(
            any(entry.message_type == "animate" for entry in self.trace.snapshot())
        )

    def test_invalid_oversized_disconnect_and_reconnect_are_visible(self) -> None:
        initial_connection = self._state()["connection_id"]
        self.device.inject("{bad json")
        self.device.inject("x" * 2_050)
        wait_for(
            lambda: any(not entry.accepted for entry in self.trace.snapshot()),
            "invalid input was not traced",
        )
        results = {entry.result for entry in self.trace.snapshot()}
        self.assertIn("bad_json", results)
        self.assertIn("line_too_long", results)

        self.device.disconnect()
        wait_for(lambda: not bool(self._state()["connected"]), "did not disconnect")
        self.device.connect()
        wait_for(
            lambda: (
                bool(self._state()["connected"])
                and self._state()["connection_id"] != initial_connection
            ),
            "did not reconnect with a fresh session",
        )
        wait_for(lambda: self._screen() is Screen.HOME, "view was not restored")

    def test_stale_control_epoch_crosses_codec_but_cannot_navigate(self) -> None:
        state = self._state()
        connection_id = state["connection_id"]
        boot_id = state["boot_id"]
        view = cast_view(state)
        epoch = view["control_epoch"]
        if not isinstance(epoch, int):
            raise AssertionError("control epoch is not an integer")
        self.device.inject(
            "{"
            f'"v":2,"type":"button","connection_id":"{connection_id}",'
            f'"boot_id":"{boot_id}","seq":1,"control_epoch":{epoch - 1},'
            '"button":2,"action":"press"}'
        )
        time.sleep(0.05)

        self.assertIs(self._screen(), Screen.HOME)
        self.assertTrue(
            any(
                entry.message_type == "button"
                and entry.result == "stale_control_epoch"
                and not entry.accepted
                for entry in self.trace.snapshot()
            )
        )

    def test_web_server_binds_loopback_and_exposes_state(self) -> None:
        servers: list[FakeHttpServer] = []

        def build_server(address: tuple[str, int], handler: object) -> FakeHttpServer:
            server = FakeHttpServer(address, handler)
            servers.append(server)
            return server

        with (
            patch(
                "deskpet.adapters.simulator_web.ThreadingHTTPServer",
                side_effect=build_server,
            ),
            patch("builtins.print"),
        ):
            server = SimulatorWebServer(self.device, 8765)
            server.start()
            server.stop()

        self.assertEqual(servers[0].requested_address, ("127.0.0.1", 8765))
        self.assertEqual(server.url, "http://127.0.0.1:8765")

    def test_web_ui_keeps_buttons_stable_and_respects_trace_scrolling(self) -> None:
        self.assertNotIn("textContent='Hold'", SIMULATOR_HTML)
        self.assertIn("buttonSignature", SIMULATOR_HTML)
        self.assertIn("view.focus_minutes+' min'", SIMULATOR_HTML)
        self.assertIn("'break: '+view.break_minutes+' min'", SIMULATOR_HTML)
        self.assertIn("const stickToBottom=!current.trace_paused", SIMULATOR_HTML)
        self.assertIn("gesture:'hold'", SIMULATOR_HTML)
        self.assertIn("Camera: ", SIMULATOR_HTML)


def cast_view(state: dict[str, object]) -> dict[str, object]:
    view = state["view"]
    if not isinstance(view, dict):
        raise AssertionError("simulator has no view")
    return cast_view_value(cast(dict[object, object], view))


def cast_view_value(view: dict[object, object]) -> dict[str, object]:
    if not all(isinstance(key, str) for key in view):
        raise AssertionError("view keys must be strings")
    return {str(key): value for key, value in view.items()}


class FakeHttpServer:
    def __init__(
        self,
        requested_address: tuple[str, int],
        _handler: object,
    ) -> None:
        self.requested_address = requested_address
        self.server_address = requested_address

    def serve_forever(self) -> None: ...

    def shutdown(self) -> None: ...

    def server_close(self) -> None: ...


if __name__ == "__main__":
    unittest.main()
