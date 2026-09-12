"""Per-button debounce and press/hold gesture detection.

Firmware only reports "button N was pressed/held"; it never decides what
that means (see ../docs/system_design.md). Uses wrap-safe `time.ticks_diff`
throughout so a `ticks_ms()` wraparound cannot misfire a gesture.
"""

import time

from machine import Pin


class ButtonScanner:
    """GPIO/config -> scanner. One instance covers every declared button."""

    def __init__(self, buttons, debounce_ms, hold_ms):
        self._debounce_ms = debounce_ms
        self._hold_ms = hold_ms
        self._states = [self._make_state(button) for button in buttons]

    @staticmethod
    def _make_state(button):
        pull = Pin.PULL_UP if button["pull"] == "up" else Pin.PULL_DOWN
        pin = Pin(button["gpio"], Pin.IN, pull)
        return {
            "id": button["id"],
            "pin": pin,
            "active_low": button["active_low"],
            "candidate_down": False,
            "candidate_since": 0,
            "stable_down": False,
            "down_since": 0,
            "epoch": 0,
            "hold_fired": False,
            "suppressed": False,
        }

    def reset_until_release(self):
        """Suppress already-held buttons across a boot/connection reset."""
        for state in self._states:
            if self._raw_down(state):
                state["suppressed"] = True
            state["stable_down"] = False
            state["candidate_down"] = self._raw_down(state)
            state["hold_fired"] = False

    def _raw_down(self, state):
        level = state["pin"].value()
        return (level == 0) if state["active_low"] else (level == 1)

    def poll(self, now_ms, control_epoch):
        """Read pins; latch epoch at stable down; emit button/action/epoch once."""
        gestures = []
        for state in self._states:
            gesture = self._poll_one(state, now_ms, control_epoch)
            if gesture is not None:
                gestures.append(gesture)
        return gestures

    def _poll_one(self, state, now_ms, control_epoch):
        raw_down = self._raw_down(state)

        if state["suppressed"]:
            if not raw_down:
                state["suppressed"] = False
            return None

        if raw_down != state["candidate_down"]:
            state["candidate_down"] = raw_down
            state["candidate_since"] = now_ms
            return None
        if time.ticks_diff(now_ms, state["candidate_since"]) < self._debounce_ms:
            return None

        if raw_down and not state["stable_down"]:
            state["stable_down"] = True
            state["down_since"] = now_ms
            state["epoch"] = control_epoch
            state["hold_fired"] = False
            return None

        if raw_down and state["stable_down"] and not state["hold_fired"]:
            if time.ticks_diff(now_ms, state["down_since"]) >= self._hold_ms:
                state["hold_fired"] = True
                return {
                    "button": state["id"],
                    "action": "hold",
                    "control_epoch": state["epoch"],
                }
            return None

        if not raw_down and state["stable_down"]:
            state["stable_down"] = False
            if state["hold_fired"]:
                return None
            return {
                "button": state["id"],
                "action": "press",
                "control_epoch": state["epoch"],
            }

        return None
