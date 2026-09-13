"""Tests for versioned focus rewards and the infinite level curve."""

import unittest

from deskpet.core.commands import Accepted, Rejected
from deskpet.core.events import FocusRewardGranted
from deskpet.core.models import (
    AttentionSummary,
    BreakOffer,
    GameState,
    KeyboardSummary,
    ProgressionState,
    level_for_xp,
    xp_for_next_level,
    xp_into_level,
)
from deskpet.features.rewards import RewardPolicy, decide

POLICY = RewardPolicy(
    version=2,
    xp_per_focus_minute=3,
    yarn_minutes_per_unit=10,
    chain_xp_percent=15,
    chain_yarn_per_step=1,
    keyboard_one_yarn_keypresses=500,
    keyboard_two_yarn_keypresses=1000,
)


def state(*, total_xp: int = 0, yarn: int = 10) -> GameState:
    return GameState(
        user_id="user-1",
        pet_id="pet-1",
        pending_break=BreakOffer("focus-1", 300, "America/Chicago"),
        progression=ProgressionState(
            total_xp=total_xp,
            level=level_for_xp(total_xp, 75, 25),
            yarn_balance=yarn,
            policy_version=2,
            xp_per_level=75,
            xp_level_increment=25,
        ),
    )


class RewardDecisionTests(unittest.TestCase):
    def test_approved_duration_and_chain_examples(self) -> None:
        examples = (
            (5, 1, 15, 1),
            (25, 1, 75, 3),
            (25, 2, 86, 4),
            (25, 3, 97, 5),
            (60, 1, 180, 6),
            (60, 3, 234, 8),
        )
        for minutes, chain, expected_xp, expected_yarn in examples:
            with self.subTest(minutes=minutes, chain=chain):
                result = decide(state(), "focus-1", minutes, chain, POLICY)
                self.assertIsInstance(result, Accepted)
                assert isinstance(result, Accepted)
                event = result.event
                self.assertIsInstance(event, FocusRewardGranted)
                assert isinstance(event, FocusRewardGranted)
                self.assertEqual(event.base_xp + event.chain_xp, expected_xp)
                self.assertEqual(event.base_yarn + event.chain_yarn, expected_yarn)
                self.assertEqual(event.dedupe_key, "focus-reward:focus-1")

    def test_debug_zero_minute_completion_grants_no_base_reward(self) -> None:
        result = decide(state(), "focus-1", 0, 1, POLICY)

        self.assertIsInstance(result, Accepted)
        assert isinstance(result, Accepted)
        event = result.event
        self.assertIsInstance(event, FocusRewardGranted)
        assert isinstance(event, FocusRewardGranted)
        self.assertEqual(event.base_xp, 0)
        self.assertEqual(event.base_yarn, 0)

    def test_wrong_or_missing_completion_is_unavailable(self) -> None:
        missing = GameState(
            user_id="user-1",
            pet_id="pet-1",
            progression=state().progression,
        )
        self.assertIsInstance(decide(missing, "focus-1", 25, 1, POLICY), Rejected)
        self.assertIsInstance(decide(state(), "other", 25, 1, POLICY), Rejected)

    def test_keyboard_bonus_has_approved_boundaries_and_never_adds_xp(self) -> None:
        for count, expected_yarn in (
            (0, 0),
            (499, 0),
            (500, 1),
            (999, 1),
            (1000, 2),
            (5000, 2),
        ):
            with self.subTest(count=count):
                result = decide(
                    state(),
                    "focus-1",
                    25,
                    1,
                    POLICY,
                    KeyboardSummary(count, True),
                )
                assert isinstance(result, Accepted)
                event = result.event
                assert isinstance(event, FocusRewardGranted)
                self.assertEqual(event.keyboard_yarn, expected_yarn)
                self.assertEqual(event.total_xp_after, 75)

        unavailable = decide(
            state(), "focus-1", 25, 1, POLICY, KeyboardSummary(0, False)
        )
        assert isinstance(unavailable, Accepted)
        unavailable_event = unavailable.event
        assert isinstance(unavailable_event, FocusRewardGranted)
        self.assertTrue(unavailable_event.keyboard_enabled)
        self.assertFalse(unavailable_event.keyboard_available)
        self.assertEqual(unavailable_event.keyboard_yarn, 0)

    def test_camera_bonus_requires_coverage_and_uses_attention_tiers(self) -> None:
        cases = (
            (AttentionSummary(10, 5, 5, True), 0),
            (AttentionSummary(10, 6, 4, True), 0),
            (AttentionSummary(10, 6, 5, True), 1),
            (AttentionSummary(10, 10, 9, True), 2),
            (AttentionSummary(100, 100, 100, True), 2),
            (AttentionSummary(0, 0, 0, False), 0),
        )
        for summary, expected_yarn in cases:
            with self.subTest(summary=summary):
                result = decide(state(), "focus-1", 25, 1, POLICY, camera=summary)
                assert isinstance(result, Accepted)
                event = result.event
                assert isinstance(event, FocusRewardGranted)
                self.assertEqual(event.camera_yarn, expected_yarn)
                self.assertEqual(event.total_xp_after, 75)


class LevelCurveTests(unittest.TestCase):
    def test_thresholds_grow_forever_and_progress_is_relative_to_level(self) -> None:
        cases = (
            (0, 1, 0, 75),
            (74, 1, 74, 75),
            (75, 2, 0, 100),
            (174, 2, 99, 100),
            (175, 3, 0, 125),
            (10_000, 26, 625, 700),
        )
        for total, level, progress, required in cases:
            with self.subTest(total=total):
                self.assertEqual(level_for_xp(total, 75, 25), level)
                self.assertEqual(xp_into_level(total, 75, 25), progress)
                self.assertEqual(xp_for_next_level(level, 75, 25), required)


if __name__ == "__main__":
    unittest.main()
