"""Tests for config-driven action resolution, labels and navigation."""

import unittest
from datetime import UTC, datetime
from pathlib import Path

from deskpet.adapters.config_loader import load
from deskpet.app.controls import ACTIONS, labels, navigate, resolve, validate_bindings
from deskpet.core.commands import BackHome, CycleDuration, FeedDefault, OpenSetup
from deskpet.core.models import (
    ButtonId,
    ClockReading,
    GameState,
    Gesture,
    RuntimeState,
    Screen,
)
from deskpet.core.views import ButtonInput, ControlContext

CONFIG_PATH = Path(__file__).parents[2] / "config.yaml"
BUTTONS = (ButtonId(1), ButtonId(2))


def runtime(screen: Screen = Screen.HOME, *, epoch: int = 1) -> RuntimeState:
    return RuntimeState(screen, 25, None, None, epoch, "connection-1", "boot-1")


def button(
    button_id: int,
    gesture: Gesture = Gesture.PRESS,
    *,
    epoch: int = 1,
) -> ButtonInput:
    return ButtonInput(
        connection_id="connection-1",
        boot_id="boot-1",
        seq=1,
        control_epoch=epoch,
        button=ButtonId(button_id),
        action=gesture,
        received_at=ClockReading(datetime(2026, 9, 13, tzinfo=UTC), 1, False),
    )


class ControlResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load(CONFIG_PATH)

    def test_default_config_resolves_and_labels_the_same_action(self) -> None:
        state = GameState("user-1", "pet-1")

        intent = resolve(button(1), runtime(), state, self.config.bindings)
        rendered = labels(
            ControlContext.HOME, state, BUTTONS, self.config.bindings, ACTIONS
        )

        self.assertIsInstance(intent, FeedDefault)
        self.assertEqual([item.label for item in rendered], ["Feed", "Focus"])

    def test_remapping_changes_behavior_and_label_together(self) -> None:
        state = GameState("user-1", "pet-1")
        remapped = dict(self.config.bindings)
        left = (ControlContext.HOME, ButtonId(1), Gesture.PRESS)
        right = (ControlContext.HOME, ButtonId(2), Gesture.PRESS)
        remapped[left], remapped[right] = remapped[right], remapped[left]

        intent = resolve(button(1), runtime(), state, remapped)
        rendered = labels(ControlContext.HOME, state, BUTTONS, remapped, ACTIONS)

        self.assertIsInstance(intent, OpenSetup)
        self.assertEqual([item.label for item in rendered], ["Focus", "Feed"])

    def test_third_button_uses_the_generic_binding_path(self) -> None:
        state = GameState("user-1", "pet-1")
        buttons = (*BUTTONS, ButtonId(3))
        bindings = dict(self.config.bindings)
        bindings[(ControlContext.HOME, ButtonId(3), Gesture.PRESS)] = next(
            action
            for action, definition in ACTIONS.items()
            if definition.label == "Feed"
        )

        validate_bindings(bindings, buttons, self.config.ui.max_buttons)
        intent = resolve(button(3), runtime(), state, bindings)
        rendered = labels(ControlContext.HOME, state, buttons, bindings, ACTIONS)

        self.assertIsInstance(intent, FeedDefault)
        self.assertEqual(rendered[2].label, "Feed")

    def test_stale_epoch_and_unavailable_action_do_nothing(self) -> None:
        state = GameState("user-1", "pet-1")
        stale = resolve(
            button(1, epoch=2), runtime(epoch=1), state, self.config.bindings
        )
        invalid_context = resolve(
            button(2), runtime(Screen.FOCUS), state, self.config.bindings
        )

        self.assertIsNone(stale)
        self.assertIsNone(invalid_context)

    def test_binding_validation_rejects_unknown_device_button_and_small_layout(
        self,
    ) -> None:
        with self.assertRaisesRegex(ValueError, "unadvertised"):
            validate_bindings(self.config.bindings, (ButtonId(1),), 3)
        with self.assertRaisesRegex(ValueError, "layout"):
            validate_bindings(self.config.bindings, BUTTONS, 1)


class NavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load(CONFIG_PATH)

    def test_open_uses_last_confirmed_duration_and_increments_epoch(self) -> None:
        state = GameState("user-1", "pet-1", last_focus_minutes=35)

        updated = navigate(runtime(), OpenSetup(), state, self.config.focus)

        self.assertIs(updated.screen, Screen.SETUP)
        self.assertEqual(updated.selected_focus_minutes, 35)
        self.assertEqual(updated.control_epoch, 2)

    def test_cycle_wraps_without_changing_control_meaning(self) -> None:
        current = runtime(Screen.SETUP, epoch=4)
        current = RuntimeState(
            current.screen,
            60,
            current.run_anchor_mono_ms,
            current.previous_clock,
            current.control_epoch,
            current.connection_id,
            current.boot_id,
        )

        updated = navigate(
            current, CycleDuration(), GameState("u", "p"), self.config.focus
        )

        self.assertEqual(updated.selected_focus_minutes, 5)
        self.assertEqual(updated.control_epoch, 4)

    def test_back_returns_home_and_increments_epoch(self) -> None:
        updated = navigate(
            runtime(Screen.SETUP, epoch=2),
            BackHome(),
            GameState("u", "p"),
            self.config.focus,
        )

        self.assertIs(updated.screen, Screen.HOME)
        self.assertEqual(updated.control_epoch, 3)


if __name__ == "__main__":
    unittest.main()
