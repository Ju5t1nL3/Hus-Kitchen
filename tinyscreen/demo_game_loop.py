"""Throwaway demo: drives the TinyScreen+ firmware through a basic loop.

This is NOT the production laptop game engine described in AGENTS.md (that
will own the real event log, game_state and pomodoro rules under a future
laptop/ directory). It exists only to exercise the ported firmware/protocol
end-to-end: connect, render a home screen, react to button presses with a
tiny in-memory focus timer, and confirm button events round-trip correctly.

Runs forever: waits for the TinyScreen+ to be plugged in (matched by USB
VID/PID, not a hardcoded COM port -- see AGENTS.md's portability rule), runs
the loop for as long as it stays connected, and goes back to waiting if it's
unplugged. Once a real laptop app exists, this auto-detect-and-reconnect
logic belongs in its own serial adapter module rather than here.

Usage: python demo_game_loop.py [COM_PORT]   (COM_PORT overrides auto-detect)
"""

import json
import sys
import threading
import time

import serial
import serial.tools.list_ports

BAUD = 115200
CONNECTION_ID = "demo-1"
BUTTON_IDS = (1, 2, 3, 4)  # must match firmware's advertised buttons exactly

FOCUS_SECONDS = 15  # short on purpose, this is a demo

# TinyScreen+ (TinyCircuits, Atmel/Microchip SAMD21) USB identifiers -- see
# the board-switch discussion in docs/design_decisions.md.
TINYSCREEN_VID = 0x03EB
TINYSCREEN_PID = 0x8009

FORCED_PORT = sys.argv[1] if len(sys.argv) > 1 else None


def find_tinyscreen_port():
    """Scan connected serial devices for the TinyScreen+'s USB VID/PID."""
    for info in serial.tools.list_ports.comports():
        if info.vid == TINYSCREEN_VID and info.pid == TINYSCREEN_PID:
            return info.device
    return None


def wait_for_port():
    """Block until the TinyScreen+ (or the forced override port) is present."""
    announced = False
    while True:
        port = FORCED_PORT or find_tinyscreen_port()
        if port:
            return port
        if not announced:
            print("Waiting for TinyScreen+ to be plugged in...")
            announced = True
        time.sleep(1.0)


def send(ser, payload):
    line = json.dumps(payload, separators=(",", ":")) + "\n"
    ser.write(line.encode("utf-8"))


def progression_payload(progression):
    return {
        "level": progression["level"],
        "xp_into_level": progression["xp_into_level"],
        "xp_for_next_level": progression["xp_for_next_level"],
        "yarn_balance": progression["yarn_balance"],
    }


def home_view(control_epoch, clock_text, progression):
    return {
        "screen": "home",
        "control_epoch": control_epoch,
        "mood": "idle",
        "clock_text": clock_text,
        "timer_seconds": None,
        "paused": False,
        "focus_minutes": None,
        "break_minutes": None,
        "feedback": None,
        "buttons": [
            {"button": 1, "label": "Focus", "enabled": True},
            {"button": 2, "label": "Feed", "enabled": True},
            {"button": 3, "label": "Settings", "enabled": True},
            {"button": 4, "label": "Pet", "enabled": False},
        ],
        "progression": progression_payload(progression),
    }


def focus_view(control_epoch, remaining, paused):
    return {
        "screen": "focus",
        "control_epoch": control_epoch,
        "mood": "idle" if paused else "working_neutral",
        "clock_text": None,
        "timer_seconds": remaining,
        "paused": paused,
        "focus_minutes": None,
        "break_minutes": None,
        "feedback": None,
        "buttons": [
            {"button": 1, "label": "Resume" if paused else "Pause", "enabled": True},
            {"button": 2, "label": "End", "enabled": True},
            {"button": 3, "label": "-", "enabled": False},
            {"button": 4, "label": "-", "enabled": False},
        ],
        "progression": None,
    }


def setup_view(control_epoch, focus_minutes, break_minutes):
    # Corner layout: Up (top-left) / OK (top-right) / Down (bottom-left) /
    # Back (bottom-right) -- Up/Down render as caret icons, OK/Back as text.
    return {
        "screen": "setup",
        "control_epoch": control_epoch,
        "mood": "idle",
        "clock_text": None,
        "timer_seconds": None,
        "paused": False,
        "focus_minutes": focus_minutes,
        "break_minutes": break_minutes,
        "feedback": None,
        "buttons": [
            {"button": 1, "label": "Up", "enabled": True},
            {"button": 2, "label": "OK", "enabled": True},
            {"button": 3, "label": "Down", "enabled": True},
            {"button": 4, "label": "Back", "enabled": True},
        ],
        "progression": None,
    }


def settings_view(control_epoch, selected_row, keyboard_enabled, keyboard_available,
                   camera_enabled, camera_available):
    return {
        "screen": "settings",
        "control_epoch": control_epoch,
        "mood": "idle",
        "clock_text": None,
        "timer_seconds": None,
        "paused": False,
        "focus_minutes": None,
        "break_minutes": None,
        "feedback": None,
        "buttons": [
            {"button": 1, "label": "Up", "enabled": True},
            {"button": 2, "label": "Select", "enabled": True},
            {"button": 3, "label": "Down", "enabled": True},
            {"button": 4, "label": "Back", "enabled": True},
        ],
        "progression": None,
        "settings": {
            "selected_row": selected_row,
            "keyboard_enabled": keyboard_enabled,
            "keyboard_available": keyboard_available,
            "camera_enabled": camera_enabled,
            "camera_available": camera_available,
        },
    }


def break_offer_view(control_epoch, earned_xp, earned_yarn):
    return {
        "screen": "break_offer",
        "control_epoch": control_epoch,
        "mood": "party",
        "clock_text": None,
        "timer_seconds": None,
        "paused": False,
        "focus_minutes": None,
        "break_minutes": None,
        "feedback": None,
        "buttons": [
            {"button": 1, "label": "Break", "enabled": True},
            {"button": 2, "label": "Home", "enabled": True},
            {"button": 3, "label": "-", "enabled": False},
            {"button": 4, "label": "-", "enabled": False},
        ],
        "progression": None,
        "earned_rewards": {"xp": earned_xp, "yarn": earned_yarn},
    }


def award_completion(progression, xp_gained=20, yarn_gained=5):
    """Mutates `progression` in place, returning the gains just awarded."""
    progression["xp_into_level"] += xp_gained
    progression["yarn_balance"] += yarn_gained
    while progression["xp_into_level"] >= progression["xp_for_next_level"]:
        progression["xp_into_level"] -= progression["xp_for_next_level"]
        progression["level"] += 1
        progression["xp_for_next_level"] = int(progression["xp_for_next_level"] * 1.15)
    return xp_gained, yarn_gained


class Reader(threading.Thread):
    """Background serial reader so button presses are seen immediately."""

    def __init__(self, ser):
        super().__init__(daemon=True)
        self._ser = ser
        self.events = []
        self._lock = threading.Lock()
        self._running = True
        self.error = None

    def run(self):
        buf = b""
        while self._running:
            try:
                chunk = self._ser.read(256)
            except (serial.SerialException, OSError) as exc:
                self.error = exc
                return
            if not chunk:
                continue
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                try:
                    message = json.loads(line.decode("utf-8"))
                except ValueError:
                    continue
                print("<-", message)
                if message.get("type") == "button":
                    with self._lock:
                        self.events.append(message)

    def drain(self):
        with self._lock:
            events, self.events = self.events, []
        return events

    def stop(self):
        self._running = False


def run_session(port):
    """Connect to `port` and drive the loop until it disconnects or errors."""
    ser = serial.Serial(port, BAUD, timeout=0.2, write_timeout=2)
    try:
        time.sleep(2.0)  # let the SAMD21 finish its post-upload/port-open reset
        ser.reset_input_buffer()

        reader = Reader(ser)
        reader.start()
        try:
            revision = 0
            control_epoch = 1

            def next_revision():
                nonlocal revision
                revision += 1
                return revision

            print("-> hello")
            send(ser, {"v": 2, "type": "hello", "connection_id": CONNECTION_ID})
            time.sleep(0.5)

            screen = "home"
            remaining = FOCUS_SECONDS
            paused = False
            break_offer_until = None
            focus_minutes = 25
            break_minutes = 5
            settings_selected_row = 0
            keyboard_enabled = False
            camera_enabled = False
            # M29 landed upstream (laptop/src/deskpet/adapters/camera_tracker.py):
            # camera tracking is a real feature now, not just planned. This demo
            # stub doesn't run that adapter or probe for a webcam -- it just
            # reflects that the capability now exists, off by default.
            camera_available = True
            progression = {
                "level": 1,
                "xp_into_level": 0,
                "xp_for_next_level": 75,
                "yarn_balance": 10,
            }

            clock_text = time.strftime("%H:%M")
            send(
                ser,
                {
                    "v": 2,
                    "type": "render",
                    "connection_id": CONNECTION_ID,
                    "revision": next_revision(),
                    "view": home_view(control_epoch, clock_text, progression),
                },
            )
            print(f"-> render home (revision {revision})")

            last_tick = time.monotonic()
            last_ping = time.monotonic()
            last_port_check = time.monotonic()
            ping_nonce = 0

            while True:
                if reader.error is not None:
                    raise reader.error
                if not reader.is_alive():
                    raise serial.SerialException("reader thread exited unexpectedly")

                for event in reader.drain():
                    button, action = event["button"], event["action"]

                    if action != "press":
                        continue

                    if screen == "home" and button == 3:
                        screen = "settings"
                        control_epoch += 1
                        send(
                            ser,
                            {
                                "v": 2,
                                "type": "render",
                                "connection_id": CONNECTION_ID,
                                "revision": next_revision(),
                                "view": settings_view(
                                    control_epoch, settings_selected_row, keyboard_enabled,
                                    True, camera_enabled, camera_available
                                ),
                            },
                        )
                        print("-> opened settings")

                    elif screen == "home" and button == 1:
                        screen = "setup"
                        control_epoch += 1
                        send(
                            ser,
                            {
                                "v": 2,
                                "type": "render",
                                "connection_id": CONNECTION_ID,
                                "revision": next_revision(),
                                "view": setup_view(control_epoch, focus_minutes, break_minutes),
                            },
                        )
                        print("-> opened setup")

                    elif screen == "setup" and button == 1:
                        if focus_minutes == 0:
                            focus_minutes = 5
                        else:
                            focus_minutes = focus_minutes + 5 if focus_minutes < 60 else 5
                        break_minutes = max(1, round(focus_minutes / 5))
                        send(
                            ser,
                            {
                                "v": 2,
                                "type": "render",
                                "connection_id": CONNECTION_ID,
                                "revision": next_revision(),
                                "view": setup_view(control_epoch, focus_minutes, break_minutes),
                            },
                        )
                        print(f"-> setup: {focus_minutes}m focus / {break_minutes}m break")

                    elif screen == "setup" and button == 2:
                        screen = "focus"
                        # 0 is the reserved debug duration: a fixed 10-second
                        # session for quick local testing.
                        remaining = 10 if focus_minutes == 0 else focus_minutes * 60
                        paused = False
                        control_epoch += 1
                        send(
                            ser,
                            {
                                "v": 2,
                                "type": "render",
                                "connection_id": CONNECTION_ID,
                                "revision": next_revision(),
                                "view": focus_view(control_epoch, remaining, paused),
                            },
                        )
                        print(f"-> entered focus ({focus_minutes}m)")

                    elif screen == "setup" and button == 3:
                        if focus_minutes == 5:
                            focus_minutes = 0  # debug: fixed 10-second session
                        elif focus_minutes == 0:
                            focus_minutes = 60
                        else:
                            focus_minutes = focus_minutes - 5
                        break_minutes = max(1, round(focus_minutes / 5))
                        send(
                            ser,
                            {
                                "v": 2,
                                "type": "render",
                                "connection_id": CONNECTION_ID,
                                "revision": next_revision(),
                                "view": setup_view(control_epoch, focus_minutes, break_minutes),
                            },
                        )
                        print(f"-> setup: {focus_minutes}m focus / {break_minutes}m break")

                    elif screen == "setup" and button == 4:
                        screen = "home"
                        control_epoch += 1
                        clock_text = time.strftime("%H:%M")
                        send(
                            ser,
                            {
                                "v": 2,
                                "type": "render",
                                "connection_id": CONNECTION_ID,
                                "revision": next_revision(),
                                "view": home_view(control_epoch, clock_text, progression),
                            },
                        )
                        print("-> cancelled setup, back home")

                    elif screen == "settings" and button == 1:
                        settings_selected_row = 1 - settings_selected_row
                        send(
                            ser,
                            {
                                "v": 2,
                                "type": "render",
                                "connection_id": CONNECTION_ID,
                                "revision": next_revision(),
                                "view": settings_view(
                                    control_epoch, settings_selected_row, keyboard_enabled,
                                    True, camera_enabled, camera_available
                                ),
                            },
                        )

                    elif screen == "settings" and button == 2:
                        if settings_selected_row == 0:
                            keyboard_enabled = not keyboard_enabled
                        elif camera_available:
                            camera_enabled = not camera_enabled
                        send(
                            ser,
                            {
                                "v": 2,
                                "type": "render",
                                "connection_id": CONNECTION_ID,
                                "revision": next_revision(),
                                "view": settings_view(
                                    control_epoch, settings_selected_row, keyboard_enabled,
                                    True, camera_enabled, camera_available
                                ),
                            },
                        )
                        if settings_selected_row == 0:
                            print(f"-> keyboard {'on' if keyboard_enabled else 'off'}")
                        else:
                            print(f"-> camera {'on' if camera_enabled else 'off'}")

                    elif screen == "settings" and button == 3:
                        settings_selected_row = 1 - settings_selected_row
                        send(
                            ser,
                            {
                                "v": 2,
                                "type": "render",
                                "connection_id": CONNECTION_ID,
                                "revision": next_revision(),
                                "view": settings_view(
                                    control_epoch, settings_selected_row, keyboard_enabled,
                                    True, camera_enabled, camera_available
                                ),
                            },
                        )

                    elif screen == "settings" and button == 4:
                        screen = "home"
                        control_epoch += 1
                        clock_text = time.strftime("%H:%M")
                        send(
                            ser,
                            {
                                "v": 2,
                                "type": "render",
                                "connection_id": CONNECTION_ID,
                                "revision": next_revision(),
                                "view": home_view(control_epoch, clock_text, progression),
                            },
                        )
                        print("-> left settings, back home")

                    elif screen == "focus" and button == 1:
                        paused = not paused
                        send(
                            ser,
                            {
                                "v": 2,
                                "type": "render",
                                "connection_id": CONNECTION_ID,
                                "revision": next_revision(),
                                "view": focus_view(control_epoch, remaining, paused),
                            },
                        )
                        print("-> paused" if paused else "-> resumed")

                    elif screen == "focus" and button == 2:
                        screen = "home"
                        control_epoch += 1
                        clock_text = time.strftime("%H:%M")
                        send(
                            ser,
                            {
                                "v": 2,
                                "type": "render",
                                "connection_id": CONNECTION_ID,
                                "revision": next_revision(),
                                "view": home_view(control_epoch, clock_text, progression),
                            },
                        )
                        print("-> ended focus early, back home")

                    elif screen == "break_offer":
                        screen = "home"
                        break_offer_until = None
                        control_epoch += 1
                        clock_text = time.strftime("%H:%M")
                        send(
                            ser,
                            {
                                "v": 2,
                                "type": "render",
                                "connection_id": CONNECTION_ID,
                                "revision": next_revision(),
                                "view": home_view(control_epoch, clock_text, progression),
                            },
                        )
                        print("-> dismissed focus-complete, back home")

                    elif screen == "home" and button == 2:
                        send(
                            ser,
                            {
                                "v": 2,
                                "type": "animate",
                                "connection_id": CONNECTION_ID,
                                "animation_id": f"feed-{revision}",
                                "after_revision": revision,
                                "name": "feed",
                                "food_sprite": "food_basic",
                            },
                        )
                        print("-> feed animation cue")

                now = time.monotonic()
                if now - last_tick >= 1.0:
                    last_tick = now
                    if screen == "focus" and not paused:
                        remaining = max(0, remaining - 1)
                        send(
                            ser,
                            {
                                "v": 2,
                                "type": "render",
                                "connection_id": CONNECTION_ID,
                                "revision": next_revision(),
                                "view": focus_view(control_epoch, remaining, paused),
                            },
                        )
                        if remaining == 0:
                            screen = "break_offer"
                            control_epoch += 1
                            earned_xp, earned_yarn = award_completion(progression)
                            break_offer_until = now + 4.0
                            send(
                                ser,
                                {
                                    "v": 2,
                                    "type": "render",
                                    "connection_id": CONNECTION_ID,
                                    "revision": next_revision(),
                                    "view": break_offer_view(
                                        control_epoch, earned_xp, earned_yarn
                                    ),
                                },
                            )
                            send(
                                ser,
                                {
                                    "v": 2,
                                    "type": "animate",
                                    "connection_id": CONNECTION_ID,
                                    "animation_id": f"celebrate-{revision}",
                                    "after_revision": revision,
                                    "name": "celebrate",
                                    "food_sprite": None,
                                },
                            )
                            print(
                                f"-> focus complete! level {progression['level']}, "
                                f"{progression['xp_into_level']}/{progression['xp_for_next_level']} xp, "
                                f"{progression['yarn_balance']} yarn"
                            )
                    elif screen == "break_offer" and break_offer_until is not None:
                        if now >= break_offer_until:
                            screen = "home"
                            break_offer_until = None
                            control_epoch += 1
                            clock_text = time.strftime("%H:%M")
                            send(
                                ser,
                                {
                                    "v": 2,
                                    "type": "render",
                                    "connection_id": CONNECTION_ID,
                                    "revision": next_revision(),
                                    "view": home_view(control_epoch, clock_text, progression),
                                },
                            )
                            print("-> back home")
                    elif screen == "home":
                        new_clock = time.strftime("%H:%M")
                        if new_clock != clock_text:
                            clock_text = new_clock
                            send(
                                ser,
                                {
                                    "v": 2,
                                    "type": "render",
                                    "connection_id": CONNECTION_ID,
                                    "revision": next_revision(),
                                    "view": home_view(control_epoch, clock_text, progression),
                                },
                            )

                if now - last_ping >= 2.0:
                    last_ping = now
                    ping_nonce += 1
                    send(
                        ser,
                        {
                            "v": 2,
                            "type": "ping",
                            "connection_id": CONNECTION_ID,
                            "nonce": ping_nonce,
                        },
                    )

                if now - last_port_check >= 1.0:
                    last_port_check = now
                    if not FORCED_PORT and find_tinyscreen_port() != port:
                        raise serial.SerialException(f"{port} no longer present")

                time.sleep(0.02)
        finally:
            reader.stop()
    finally:
        ser.close()


def main():
    while True:
        port = wait_for_port()
        print(f"-> connected on {port}")
        try:
            run_session(port)
        except (serial.SerialException, OSError) as exc:
            print(f"-> disconnected ({exc}), waiting to reconnect")
            time.sleep(1.0)


if __name__ == "__main__":
    main()
