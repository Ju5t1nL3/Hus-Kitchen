"""Tests for pure feeding decisions."""

import unittest
from datetime import UTC, datetime, timedelta

from deskpet.core.commands import Accepted, FeedPet, Rejected
from deskpet.core.events import EventSource, PetFed
from deskpet.core.models import (
    BreakOffer,
    BreakTerms,
    FoodDefinition,
    GameState,
    RejectionCode,
    Session,
    SessionKind,
    SessionStatus,
)
from deskpet.features.feeding import decide

NOW = datetime(2026, 9, 13, 4, 30, tzinfo=UTC)
BASIC = FoodDefinition(id="basic", sprite_id="food_basic", content_seconds=20)
FOODS = {BASIC.id: BASIC}


def empty_state() -> GameState:
    return GameState("user-1", "pet-1")


class FeedingDecisionTests(unittest.TestCase):
    def test_basic_food_creates_free_feed_event_and_resolved_reaction(self) -> None:
        state = empty_state()

        result = decide(
            state,
            FeedPet("basic", "button:connection-1:7"),
            FOODS,
            NOW,
        )

        self.assertIsInstance(result, Accepted)
        assert isinstance(result, Accepted)
        self.assertIsInstance(result.event, PetFed)
        assert isinstance(result.event, PetFed)
        self.assertIs(result.event.source, EventSource.LOCAL_CONTROLS)
        self.assertEqual(result.event.dedupe_key, "button:connection-1:7")
        self.assertEqual(result.event.food_id, "basic")
        self.assertEqual(result.event.reaction.expires_at, NOW + timedelta(seconds=20))
        self.assertEqual(state, empty_state(), "decide must not mutate its input")

    def test_unknown_food_is_rejected(self) -> None:
        result = decide(empty_state(), FeedPet("unknown", "button:c:1"), FOODS, NOW)

        self.assertEqual(result, Rejected(RejectionCode.INVALID_FOOD))

    def test_feeding_is_unavailable_during_session_or_break_offer(self) -> None:
        session = Session(
            id="break-1",
            kind=SessionKind.BREAK,
            terms=BreakTerms(60, "focus-1", "America/Chicago"),
            status=SessionStatus.RUNNING,
            committed_active_ms=0,
        )
        active = GameState("user-1", "pet-1", active_session=session)
        offered = GameState(
            "user-1",
            "pet-1",
            pending_break=BreakOffer("focus-1", 60, "America/Chicago"),
        )

        for state in (active, offered):
            with self.subTest(state=state):
                result = decide(state, FeedPet("basic", "button:c:1"), FOODS, NOW)
                self.assertEqual(result, Rejected(RejectionCode.UNAVAILABLE))

    def test_malformed_food_mapping_fails_clearly(self) -> None:
        with self.assertRaisesRegex(ValueError, "key and id"):
            decide(
                empty_state(),
                FeedPet("basic", "button:c:1"),
                {"basic": FoodDefinition("other", "food_other", 20)},
                NOW,
            )

    def test_naive_time_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            decide(
                empty_state(),
                FeedPet("basic", "button:c:1"),
                FOODS,
                datetime(2026, 9, 13),
            )


if __name__ == "__main__":
    unittest.main()
