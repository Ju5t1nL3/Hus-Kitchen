"""Project GameState/RuntimeState into the wire-contract RenderSnapshot (M12).

presenter.build is read-only: it never mutates state or performs I/O, and it is
the only place that assembles a RenderSnapshot, so every screen matches the wire
contract in docs/serial_protocol.md by construction. presenter.on_commit decides
the next screen and any animation cues after one newly committed event, per the
navigation rules in docs/class_design.md.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import assert_never
from zoneinfo import ZoneInfo

from deskpet.app.controls import labels as resolve_labels
from deskpet.core.commands import ActionId
from deskpet.core.events import (
    BreakSessionCompleted,
    BreakSessionEnded,
    BreakSessionPaused,
    BreakSessionResumed,
    BreakSessionStarted,
    BreakSkipped,
    DomainEvent,
    FocusSessionCompleted,
    FocusSessionEnded,
    FocusSessionPaused,
    FocusSessionResumed,
    FocusSessionStarted,
    PetCreated,
    PetFed,
)
from deskpet.core.models import (
    ButtonId,
    ClockReading,
    FoodDefinition,
    GameState,
    RuntimeState,
    Screen,
    SessionStatus,
    TimerSample,
)
from deskpet.core.views import (
    ActionDefinition,
    AnimationName,
    ControlBindings,
    ControlContext,
    CueRequest,
    PresentationResult,
    RenderSnapshot,
)
from deskpet.features import emotions
from deskpet.features.timers import BreakPolicy
from deskpet.features.timers import break_minutes as compute_break_minutes


@dataclass(frozen=True, slots=True)
class PresenterConfig:
    clock_timezone: str
    break_policy: BreakPolicy


def build(
    state: GameState,
    runtime: RuntimeState,
    sample: TimerSample | None,
    now: ClockReading,
    config: PresenterConfig,
    bindings: ControlBindings,
    actions: dict[ActionId, ActionDefinition],
    device_buttons: tuple[ButtonId, ...],
) -> RenderSnapshot:
    """Build the complete snapshot for the screen currently selected in runtime."""
    paused = (
        state.active_session is not None
        and state.active_session.status is SessionStatus.PAUSED
    )
    context = _context(runtime.screen, paused)

    return RenderSnapshot(
        screen=runtime.screen,
        control_epoch=runtime.control_epoch,
        mood=emotions.select(state, now.utc),
        clock_text=_clock_text(now, config.clock_timezone)
        if runtime.screen is Screen.HOME
        else None,
        timer_seconds=_timer_seconds(runtime.screen, sample),
        paused=paused,
        focus_minutes=runtime.selected_focus_minutes
        if runtime.screen is Screen.SETUP
        else None,
        break_minutes=_break_minutes(runtime, state, config),
        buttons=resolve_labels(context, state, device_buttons, bindings, actions),
        feedback=None,
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
        case (
            FocusSessionPaused()
            | FocusSessionResumed()
            | BreakSessionPaused()
            | BreakSessionResumed()
        ):
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
        case PetFed():
            definition = food_definitions.get(draft.food_id)
            sprite = definition.sprite_id if definition is not None else None
            cue = CueRequest(name=AnimationName.FEED, food_sprite=sprite)
            return PresentationResult(screen=Screen.HOME, cues=(cue,))
        case _ as unreachable:
            assert_never(unreachable)


def _context(screen: Screen, paused: bool) -> ControlContext:
    match screen:
        case Screen.HOME:
            return ControlContext.HOME
        case Screen.SETUP:
            return ControlContext.SETUP
        case Screen.FOCUS:
            return (
                ControlContext.FOCUS_PAUSED if paused else ControlContext.FOCUS_RUNNING
            )
        case Screen.BREAK_OFFER:
            return ControlContext.BREAK_OFFER
        case Screen.BREAK:
            return (
                ControlContext.BREAK_PAUSED if paused else ControlContext.BREAK_RUNNING
            )
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
