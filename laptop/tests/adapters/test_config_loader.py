"""Tests for the YAML-to-typed-configuration boundary."""

import tempfile
import unittest
from pathlib import Path

from deskpet.adapters.config_loader import ConfigError, load
from deskpet.app.controls import validate_bindings
from deskpet.core.models import ButtonId

CONFIG_PATH = Path(__file__).parents[2] / "config.yaml"


class ConfigLoaderTests(unittest.TestCase):
    def test_repository_config_loads_and_validates_for_default_device(self) -> None:
        config = load(CONFIG_PATH)

        self.assertEqual(config.focus.default_minutes, 25)
        self.assertEqual(config.feeding.definitions["jollof_rice"].price_yarn, 3)
        self.assertEqual(config.feeding.definitions["espresso"].price_yarn, 2)
        self.assertEqual(config.device.usb_vid, 0x03EB)
        self.assertEqual(config.device.usb_pid, 0x8009)
        self.assertEqual(config.ui.max_buttons, 4)
        self.assertEqual(config.progression.starting_yarn, 10)
        self.assertEqual(config.progression.xp_per_level, 75)
        self.assertEqual(config.progression.xp_level_increment, 25)
        self.assertEqual(config.progression.xp_per_focus_minute, 3)
        validate_bindings(
            config.bindings,
            (ButtonId(1), ButtonId(2), ButtonId(3), ButtonId(4)),
            config.ui.max_buttons,
        )

    def test_unknown_action_has_a_field_specific_error(self) -> None:
        text = CONFIG_PATH.read_text(encoding="utf-8").replace(
            "1.press: open_setup", "1.press: nonexistent_action", 1
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text(text, encoding="utf-8")

            with self.assertRaisesRegex(ConfigError, "unknown action ID"):
                load(path)

    def test_invalid_default_duration_fails_at_load(self) -> None:
        text = CONFIG_PATH.read_text(encoding="utf-8").replace(
            "default_minutes: 25", "default_minutes: 7", 1
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text(text, encoding="utf-8")

            with self.assertRaisesRegex(ConfigError, "default_minutes"):
                load(path)

    def test_duplicate_yaml_key_is_rejected_instead_of_overwritten(self) -> None:
        text = CONFIG_PATH.read_text(encoding="utf-8").replace(
            "    home:\n      1.press: open_setup",
            "    home:\n      1.press: open_setup\n      1.press: open_feed",
            1,
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text(text, encoding="utf-8")

            with self.assertRaisesRegex(ConfigError, "duplicate configuration key"):
                load(path)

    def test_missing_file_is_actionable(self) -> None:
        with self.assertRaisesRegex(ConfigError, "cannot read configuration"):
            load(CONFIG_PATH.with_name("missing.yaml"))


if __name__ == "__main__":
    unittest.main()
