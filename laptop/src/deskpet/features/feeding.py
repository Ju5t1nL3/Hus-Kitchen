"""Pure feeding decisions for the one-food MVP."""

from collections.abc import Mapping
from datetime import datetime, timedelta

from deskpet.core.commands import Accepted, Decision, FeedPet, Rejected
from deskpet.core.events import EventSource, PetFed
from deskpet.core.models import (
    FoodDefinition,
    GameState,
    Reaction,
    ReactionMood,
    RejectionCode,
)


def decide(
    state: GameState,
    command: FeedPet,
    food_definitions: Mapping[str, FoodDefinition],
    now_utc: datetime,
) -> Decision:
    """Validate a feed request and return one free feeding event draft."""
    _require_aware(now_utc)
    if state.active_session is not None or state.pending_break is not None:
        return Rejected(RejectionCode.UNAVAILABLE)

    food = food_definitions.get(command.food_id)
    if food is None:
        return Rejected(RejectionCode.INVALID_FOOD)
    if food.id != command.food_id:
        raise ValueError("food definition key and id do not match")

    return Accepted(
        PetFed(
            source=EventSource.LOCAL_CONTROLS,
            dedupe_key=command.operation_key,
            food_id=food.id,
            reaction=Reaction(
                mood=ReactionMood.CONTENT,
                expires_at=now_utc + timedelta(seconds=food.content_seconds),
            ),
        )
    )


def _require_aware(now_utc: datetime) -> None:
    if now_utc.tzinfo is None or now_utc.utcoffset() is None:
        raise ValueError("now_utc must be timezone-aware")
