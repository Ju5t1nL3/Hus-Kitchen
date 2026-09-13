"""Pure, atomic purchase-and-feed decisions."""

from collections.abc import Mapping
from datetime import datetime, timedelta

from deskpet.core.commands import Accepted, Decision, FeedPet, Rejected
from deskpet.core.events import EventSource, ItemPurchasedAndFed
from deskpet.core.models import (
    FoodDefinition,
    GameState,
    Reaction,
    ReactionMood,
    RejectionCode,
)
from deskpet.features.emotions import is_hungry


def decide(
    state: GameState,
    command: FeedPet,
    food_definitions: Mapping[str, FoodDefinition],
    now_utc: datetime,
    hunger_seconds: int = 300,
) -> Decision:
    """Resolve price, spend yarn and feed in one replayable event draft."""
    _require_aware(now_utc)
    if state.active_session is not None or state.pending_break is not None:
        return Rejected(RejectionCode.UNAVAILABLE)
    if state.needs_comfort:
        return Rejected(RejectionCode.UNAVAILABLE)

    food = food_definitions.get(command.food_id)
    if food is None:
        return Rejected(RejectionCode.INVALID_FOOD)
    if food.id != command.food_id:
        raise ValueError("food definition key and id do not match")
    progression = state.progression
    if progression is None:
        return Rejected(RejectionCode.UNAVAILABLE)
    if progression.yarn_balance < food.price_yarn:
        return Rejected(RejectionCode.INSUFFICIENT_YARN)
    if not is_hungry(state, now_utc, hunger_seconds):
        return Rejected(RejectionCode.UNAVAILABLE)

    return Accepted(
        ItemPurchasedAndFed(
            source=EventSource.LOCAL_CONTROLS,
            dedupe_key=command.operation_key,
            item_id=food.id,
            price_paid=food.price_yarn,
            yarn_balance_after=progression.yarn_balance - food.price_yarn,
            reaction=Reaction(
                mood=ReactionMood.HAPPY,
                expires_at=now_utc + timedelta(seconds=food.happy_seconds),
            ),
        )
    )


def _require_aware(now_utc: datetime) -> None:
    if now_utc.tzinfo is None or now_utc.utcoffset() is None:
        raise ValueError("now_utc must be timezone-aware")
