"""Tests for durable, explicit activity-tracking and sound preferences."""

import unittest
from dataclasses import replace

from deskpet.core.commands import Accepted, Rejected
from deskpet.core.events import SoundPreferenceChanged, TrackingPreferencesChanged
from deskpet.core.models import BreakOffer, GameState
from deskpet.features.preferences import decide_toggle, decide_toggle_sound


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

    def test_sound_row_toggles_via_decide_toggle(self) -> None:
        result = decide_toggle(self.state, 2, "button:c:1", camera_available=False)

        self.assertIsInstance(result, Accepted)
        assert isinstance(result, Accepted)
        event = result.event
        self.assertIsInstance(event, SoundPreferenceChanged)
        assert isinstance(event, SoundPreferenceChanged)
        self.assertFalse(event.sound_enabled)

    def test_sound_toggle_is_always_available(self) -> None:
        result = decide_toggle_sound(self.state, "button:c:1")

        self.assertIsInstance(result, Accepted)
        assert isinstance(result, Accepted)
        event = result.event
        self.assertIsInstance(event, SoundPreferenceChanged)
        assert isinstance(event, SoundPreferenceChanged)
        self.assertFalse(event.sound_enabled)

    def test_sound_toggle_rejected_mid_session(self) -> None:
        busy = replace(self.state, pending_break=BreakOffer("focus-1", 5, "UTC"))
        result = decide_toggle_sound(busy, "button:c:1")

        self.assertIsInstance(result, Rejected)


if __name__ == "__main__":
    unittest.main()
