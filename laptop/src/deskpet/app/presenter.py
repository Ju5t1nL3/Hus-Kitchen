"""Project GameState/RuntimeState into the wire-contract RenderSnapshot (M12).

presenter.build is read-only: it never mutates state or performs I/O, and it is
the only place that assembles a RenderSnapshot, so every screen matches the wire
contract in docs/serial_protocol.md by construction. presenter.on_commit decides
the next screen and any animation cues after one newly committed event, per the
navigation rules in docs/class_design.md.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import assert_never
from zoneinfo import ZoneInfo

from deskpet.app.controls import labels as resolve_labels
from deskpet.core.commands import ActionId, BuyItem
from deskpet.core.events import (
    BreakSessionCompleted,
    BreakSessionEnded,
    BreakSessionStarted,
    BreakSkipped,
    DomainEvent,
    FocusRewardGranted,
    FocusSessionCompleted,
    FocusSessionEnded,
    FocusSessionPaused,
    FocusSessionResumed,
    FocusSessionStarted,
    ItemPurchasedAndFed,
    PetComforted,
    PetCreated,
    PetFed,
    ProgressionInitialized,
)
from deskpet.core.models import (
    ButtonId,
    ClockReading,
    FoodDefinition,
    GameState,
    Gesture,
    RuntimeState,
    Screen,
    SessionStatus,
    TimerSample,
    xp_for_next_level,
    xp_into_level,
)
from deskpet.core.views import (
    ActionDefinition,
    AnimationName,
    ButtonLabel,
    ControlBindings,
    ControlContext,
    CueRequest,
    EarnedRewardsView,
    PresentationResult,
    ProgressionView,
    RenderSnapshot,
)
from deskpet.features import emotions
from deskpet.features.timers import BreakPolicy
from deskpet.features.timers import break_minutes as compute_break_minutes


def _empty_food_definitions() -> Mapping[str, FoodDefinition]:
    return {}


@dataclass(frozen=True, slots=True)
class PresenterConfig:
    clock_timezone: str
    break_policy: BreakPolicy
    food_definitions: Mapping[str, FoodDefinition] = field(
        default_factory=_empty_food_definitions
    )
    hunger_seconds: int = 300


def build(
    state: GameState,
    runtime: RuntimeState,
    sample: TimerSample | None,
    now: ClockReading,
    config: PresenterConfig,
    bindings: ControlBindings,
    actions: Mapping[ActionId, ActionDefinition],
    device_buttons: tuple[ButtonId, ...],
) -> RenderSnapshot:
    """Build the complete snapshot for the screen currently selected in runtime."""
    paused = (
        state.active_session is not None
        and state.active_session.status is SessionStatus.PAUSED
    )
    context = _context(runtime.screen, paused)
    revealing_clock = (
        runtime.screen is Screen.FOCUS
        and runtime.clock_reveal_until_mono_ms is not None
        and now.monotonic_ms < runtime.clock_reveal_until_mono_ms
    )

    return RenderSnapshot(
        screen=runtime.screen,
        control_epoch=runtime.control_epoch,
        mood=emotions.select(state, now.utc, runtime, config.hunger_seconds),
        clock_text=_clock_text(now, config.clock_timezone)
        if runtime.screen is Screen.HOME or revealing_clock
        else None,
        timer_seconds=None
        if revealing_clock
        else _timer_seconds(runtime.screen, sample),
        paused=paused,
        focus_minutes=runtime.selected_focus_minutes
        if runtime.screen is Screen.SETUP
        else None,
        break_minutes=_break_minutes(runtime, state, config),
        buttons=_buttons(
            context,
            state,
            device_buttons,
            bindings,
            actions,
            config,
            runtime.screen,
            now,
        ),
        feedback=runtime.feedback,
        progression=_progression(state)
        if runtime.screen in {Screen.HOME, Screen.FEED}
        else None,
        earned_rewards=_earned_rewards(runtime)
        if runtime.screen is Screen.BREAK_OFFER
        else None,
    )


def on_commit(
    event: DomainEvent,
    runtime: RuntimeState,
    food_definitions: Mapping[str, FoodDefinition],
) -> PresentationResult:
    """Decide the next screen and any animation cues after one committed event."""
    draft = event.event.draft
    match draft:
        case FocusSessionStarted():
            return PresentationResult(screen=Screen.FOCUS, cues=())
        case BreakSessionStarted():
            return PresentationResult(screen=Screen.BREAK, cues=())
        case FocusSessionPaused() | FocusSessionResumed():
            return PresentationResult(screen=runtime.screen, cues=())
        case FocusSessionCompleted():
            cue = CueRequest(name=AnimationName.CELEBRATE, food_sprite=None)
            return PresentationResult(screen=Screen.BREAK_OFFER, cues=(cue,))
        case (
            FocusSessionEnded()
            | BreakSessionEnded()
            | BreakSessionCompleted()
            | BreakSkipped()
        ):
            return PresentationResult(screen=Screen.HOME, cues=())
        case PetCreated():
            return PresentationResult(screen=Screen.HOME, cues=())
        case PetComforted():
            return PresentationResult(screen=Screen.HOME, cues=())
        case ProgressionInitialized():
            return PresentationResult(screen=runtime.screen, cues=())
        case FocusRewardGranted():
            return PresentationResult(screen=runtime.screen, cues=())
        case PetFed():
            definition = food_definitions.get(draft.food_id)
            sprite = definition.sprite_id if definition is not None else None
            cue = CueRequest(name=AnimationName.FEED, food_sprite=sprite)
            return PresentationResult(screen=Screen.HOME, cues=(cue,))
        case ItemPurchasedAndFed():
            definition = food_definitions.get(draft.item_id)
            sprite = definition.sprite_id if definition is not None else None
            animation = (
                AnimationName(definition.consume_animation)
                if definition is not None
                else AnimationName.FEED
            )
            cue = CueRequest(name=animation, food_sprite=sprite)
            return PresentationResult(screen=Screen.HOME, cues=(cue,))
        case _ as unreachable:
            assert_never(unreachable)


def _context(screen: Screen, paused: bool) -> ControlContext:
    match screen:
        case Screen.HOME:
            return ControlContext.HOME
        case Screen.FEED:
            return ControlContext.FEED
        case Screen.SETUP:
            return ControlContext.SETUP
        case Screen.FOCUS:
            return (
                ControlContext.FOCUS_PAUSED if paused else ControlContext.FOCUS_RUNNING
            )
        case Screen.BREAK_OFFER:
            return ControlContext.BREAK_OFFER
        case Screen.BREAK:
            return ControlContext.BREAK_RUNNING
        case _ as unreachable:
            assert_never(unreachable)


def _clock_text(now: ClockReading, timezone: str) -> str:
    return now.utc.astimezone(ZoneInfo(timezone)).strftime("%H:%M")


def _timer_seconds(screen: Screen, sample: TimerSample | None) -> int | None:
    if screen not in (Screen.FOCUS, Screen.BREAK) or sample is None:
        return None
    return sample.remaining_seconds


def _break_minutes(
    runtime: RuntimeState, state: GameState, config: PresenterConfig
) -> int | None:
    if runtime.screen is Screen.SETUP:
        return compute_break_minutes(
            runtime.selected_focus_minutes, config.break_policy
        )
    if runtime.screen is Screen.BREAK_OFFER and state.pending_break is not None:
        return state.pending_break.duration_seconds // 60
    return None


def _progression(state: GameState) -> ProgressionView | None:
    value = state.progression
    if value is None:
        return None
    return ProgressionView(
        level=value.level,
        xp_into_level=xp_into_level(
            value.total_xp, value.xp_per_level, value.xp_level_increment
        ),
        xp_for_next_level=xp_for_next_level(
            value.level, value.xp_per_level, value.xp_level_increment
        ),
        yarn_balance=value.yarn_balance,
    )


def _earned_rewards(runtime: RuntimeState) -> EarnedRewardsView | None:
    if runtime.last_earned_xp is None or runtime.last_earned_yarn is None:
        return None
    return EarnedRewardsView(runtime.last_earned_xp, runtime.last_earned_yarn)


def _buttons(
    context: ControlContext,
    state: GameState,
    device_buttons: tuple[ButtonId, ...],
    bindings: ControlBindings,
    actions: Mapping[ActionId, ActionDefinition],
    config: PresenterConfig,
    screen: Screen,
    now: ClockReading,
) -> tuple[ButtonLabel, ...]:
    labels = resolve_labels(context, state, device_buttons, bindings, actions)
    if screen is Screen.HOME:
        updated_home: list[ButtonLabel] = []
        for label in labels:
            action_id = bindings.get((context, label.button, Gesture.PRESS))
            if action_id is ActionId.OPEN_FEED:
                updated_home.append(
                    ButtonLabel(
                        label.button,
                        label.label,
                        not state.needs_comfort,
                    )
                )
            elif action_id is ActionId.PET:
                updated_home.append(
                    ButtonLabel(
                        label.button,
                        label.label if state.needs_comfort else "-",
                        state.needs_comfort,
                    )
                )
            else:
                updated_home.append(label)
        return tuple(updated_home)
    if screen is not Screen.FEED:
        return labels
    updated: list[ButtonLabel] = []
    for label in labels:
        action_id = bindings.get((context, label.button, Gesture.PRESS))
        action = actions.get(action_id) if action_id is not None else None
        if action is None or not isinstance(action.intent, BuyItem):
            updated.append(label)
            continue
        item = config.food_definitions.get(action.intent.item_id)
        if item is None:
            updated.append(ButtonLabel(label.button, label.label, False))
            continue
        progression = state.progression
        enabled = (
            progression is not None and progression.yarn_balance >= item.price_yarn
        )
        display_name = item.display_name or item.id
        short_name = "Jollof" if item.id == "jollof_rice" else display_name
        updated.append(
            ButtonLabel(label.button, f"{short_name} {item.price_yarn}Y", enabled)
        )
    return tuple(updated)
