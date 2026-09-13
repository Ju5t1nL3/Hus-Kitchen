"""Tests for durable, explicit activity-tracking consent decisions."""

import unittest
from dataclasses import replace

from deskpet.core.commands import Accepted, Rejected
from deskpet.core.events import TrackingPreferencesChanged
from deskpet.core.models import GameState
from deskpet.features.preferences import decide_toggle


class PreferenceDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = GameState(user_id="user-1", pet_id="pet-1")

    def test_keyboard_toggles_without_changing_camera(self) -> None:
        result = decide_toggle(self.state, 0, "button:c:1", camera_available=False)

        self.assertIsInstance(result, Accepted)
        assert isinstance(result, Accepted)
        event = result.event
        self.assertIsInstance(event, TrackingPreferencesChanged)
        assert isinstance(event, TrackingPreferencesChanged)
        self.assertTrue(event.keyboard_enabled)
        self.assertFalse(event.camera_enabled)

    def test_unavailable_camera_cannot_be_enabled(self) -> None:
        result = decide_toggle(self.state, 1, "button:c:1", camera_available=False)

        self.assertIsInstance(result, Rejected)

    def test_unavailable_camera_can_still_be_disabled(self) -> None:
        enabled = replace(self.state, camera_tracking_enabled=True)
        result = decide_toggle(enabled, 1, "button:c:2", camera_available=False)
        self.assertIsInstance(result, Accepted)
        assert isinstance(result, Accepted)
        event = result.event
        self.assertIsInstance(event, TrackingPreferencesChanged)
        assert isinstance(event, TrackingPreferencesChanged)
        self.assertFalse(event.camera_enabled)


if __name__ == "__main__":
    unittest.main()
