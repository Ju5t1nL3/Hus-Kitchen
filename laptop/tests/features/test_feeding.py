"""Tests for pure feeding decisions."""

import unittest
from datetime import UTC, datetime, timedelta

from deskpet.core.commands import Accepted, FeedPet, Rejected
from deskpet.core.events import EventSource, ItemPurchasedAndFed
from deskpet.core.models import (
    BreakOffer,
    BreakTerms,
    FoodDefinition,
    GameState,
    ProgressionState,
    RejectionCode,
    Session,
    SessionKind,
    SessionStatus,
)
from deskpet.features.feeding import decide

NOW = datetime(2026, 9, 13, 4, 30, tzinfo=UTC)
BASIC = FoodDefinition(
    id="jollof_rice",
    sprite_id="jollof_rice",
    content_seconds=30,
    display_name="Jollof Rice",
    price_yarn=3,
)
FOODS = {BASIC.id: BASIC}


def empty_state() -> GameState:
    return GameState(
        "user-1",
        "pet-1",
        progression=ProgressionState(0, 1, 10, 1, 100),
        last_fed_at=NOW,
    )


class FeedingDecisionTests(unittest.TestCase):
    def test_purchase_records_resolved_price_balance_and_happy_reaction(self) -> None:
        state = empty_state()

        result = decide(
            state,
            FeedPet("jollof_rice", "button:connection-1:7"),
            FOODS,
            NOW,
        )

        self.assertIsInstance(result, Accepted)
        assert isinstance(result, Accepted)
        self.assertIsInstance(result.event, ItemPurchasedAndFed)
        assert isinstance(result.event, ItemPurchasedAndFed)
        self.assertIs(result.event.source, EventSource.LOCAL_CONTROLS)
        self.assertEqual(result.event.dedupe_key, "button:connection-1:7")
        self.assertEqual(result.event.item_id, "jollof_rice")
        self.assertEqual(result.event.price_paid, 3)
        self.assertEqual(result.event.yarn_balance_after, 7)
        self.assertEqual(result.event.reaction.expires_at, NOW + timedelta(seconds=30))
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
                result = decide(state, FeedPet("jollof_rice", "button:c:1"), FOODS, NOW)
                self.assertEqual(result, Rejected(RejectionCode.UNAVAILABLE))

    def test_malformed_food_mapping_fails_clearly(self) -> None:
        with self.assertRaisesRegex(ValueError, "key and id"):
            decide(
                empty_state(),
                FeedPet("jollof_rice", "button:c:1"),
                {"jollof_rice": FoodDefinition("other", "food_other", 20)},
                NOW,
            )

    def test_naive_time_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            decide(
                empty_state(),
                FeedPet("jollof_rice", "button:c:1"),
                FOODS,
                datetime(2026, 9, 13),
            )

    def test_insufficient_yarn_is_rejected_without_mutation(self) -> None:
        state = GameState(
            "user-1", "pet-1", progression=ProgressionState(0, 1, 2, 1, 100)
        )

        result = decide(state, FeedPet("jollof_rice", "button:c:1"), FOODS, NOW)

        self.assertEqual(result, Rejected(RejectionCode.INSUFFICIENT_YARN))
        self.assertEqual(state.progression.yarn_balance if state.progression else -1, 2)


if __name__ == "__main__":
    unittest.main()
