"""Canonical actions, configurable bindings, labels and setup navigation."""

from collections.abc import Mapping
from dataclasses import replace
from types import MappingProxyType

from deskpet.core.commands import (
    ActionId,
    BackHome,
    BuyItem,
    ConfirmFocus,
    ControlIntent,
    CycleDuration,
    EndCurrent,
    OpenFeed,
    OpenSetup,
    PauseCurrent,
    RestartFocus,
    ResumeCurrent,
    ShowTime,
    SkipBreakIntent,
    StartBreakIntent,
)
from deskpet.core.config import FocusConfig
from deskpet.core.models import (
    ButtonId,
    ClockReading,
    GameState,
    Gesture,
    RuntimeState,
    Screen,
    SessionStatus,
)
from deskpet.core.views import (
    ActionDefinition,
    ButtonInput,
    ButtonLabel,
    ControlBindings,
    ControlContext,
)
from deskpet.features.timers import next_focus_minutes

_UNBOUND_LABEL = "-"


def _idle(state: GameState) -> bool:
    return state.active_session is None and state.pending_break is None


def _has_session(state: GameState) -> bool:
    return state.active_session is not None


def _running(state: GameState) -> bool:
    return (
        state.active_session is not None
        and state.active_session.status is SessionStatus.RUNNING
    )


def _paused(state: GameState) -> bool:
    return (
        state.active_session is not None
        and state.active_session.status is SessionStatus.PAUSED
    )


def _has_break_offer(state: GameState) -> bool:
    return state.active_session is None and state.pending_break is not None


def _can_restart_focus(state: GameState) -> bool:
    return state.last_focus_minutes is not None


ACTIONS: Mapping[ActionId, ActionDefinition] = MappingProxyType(
    {
        ActionId.OPEN_FEED: ActionDefinition(
            ActionId.OPEN_FEED, "Feed", OpenFeed(), _idle
        ),
        ActionId.BUY_JOLLOF: ActionDefinition(
            ActionId.BUY_JOLLOF, "Jollof", BuyItem("jollof_rice"), _idle
        ),
        ActionId.BUY_COFFEE: ActionDefinition(
            ActionId.BUY_COFFEE, "Coffee", BuyItem("coffee"), _idle
        ),
        ActionId.OPEN_SETUP: ActionDefinition(
            ActionId.OPEN_SETUP, "Focus", OpenSetup(), _idle
        ),
        ActionId.CYCLE_DURATION: ActionDefinition(
            ActionId.CYCLE_DURATION, "Up", CycleDuration(), _idle
        ),
        ActionId.CONFIRM_FOCUS: ActionDefinition(
            ActionId.CONFIRM_FOCUS, "Set", ConfirmFocus(), _idle
        ),
        ActionId.END_CURRENT: ActionDefinition(
            ActionId.END_CURRENT, "End", EndCurrent(), _has_session
        ),
        ActionId.PAUSE_CURRENT: ActionDefinition(
            ActionId.PAUSE_CURRENT, "Pause", PauseCurrent(), _running
        ),
        ActionId.RESUME_CURRENT: ActionDefinition(
            ActionId.RESUME_CURRENT, "Resume", ResumeCurrent(), _paused
        ),
        ActionId.SKIP_BREAK: ActionDefinition(
            ActionId.SKIP_BREAK, "Home", SkipBreakIntent(), _has_break_offer
        ),
        ActionId.START_BREAK: ActionDefinition(
            ActionId.START_BREAK, "Break", StartBreakIntent(), _has_break_offer
        ),
        ActionId.BACK_HOME: ActionDefinition(
            ActionId.BACK_HOME, "Back", BackHome(), _idle
        ),
        ActionId.SHOW_TIME: ActionDefinition(
            ActionId.SHOW_TIME, "Time", ShowTime(), _has_session
        ),
        ActionId.RESTART_FOCUS: ActionDefinition(
            ActionId.RESTART_FOCUS, "Again", RestartFocus(), _can_restart_focus
        ),
        ActionId.END_BREAK: ActionDefinition(
            ActionId.END_BREAK, "Home", EndCurrent(), _has_session
        ),
    }
)


def labels(
    context: ControlContext,
    state: GameState,
    device_buttons: tuple[ButtonId, ...],
    bindings: ControlBindings,
    actions: Mapping[ActionId, ActionDefinition],
) -> tuple[ButtonLabel, ...]:
    """Derive one label per advertised button for the given control context."""
    return tuple(
        _label_for(context, button, state, bindings, actions)
        for button in device_buttons
    )


def resolve(
    button: ButtonInput,
    runtime: RuntimeState,
    state: GameState,
    bindings: ControlBindings,
    actions: Mapping[ActionId, ActionDefinition] = ACTIONS,
) -> ControlIntent | None:
    """Resolve a current, bound and available physical gesture to one intent."""
    if button.control_epoch != runtime.control_epoch:
        return None
    action_id = bindings.get(
        (context_for(runtime.screen, state), button.button, button.action)
    )
    if action_id is None:
        return None
    action = actions.get(action_id)
    if action is None or not action.available(state):
        return None
    return action.intent


_CLOCK_REVEAL_MS = 5_000


def navigate(
    runtime: RuntimeState,
    intent: OpenFeed | OpenSetup | CycleDuration | BackHome | ShowTime,
    state: GameState,
    config: FocusConfig,
    now: ClockReading | None = None,
) -> RuntimeState:
    """Apply navigation-only intents without changing durable game state."""
    match intent:
        case OpenFeed():
            return replace(
                runtime,
                screen=Screen.FEED,
                control_epoch=runtime.control_epoch + 1,
            )
        case OpenSetup():
            selected = state.last_focus_minutes or config.default_minutes
            return replace(
                runtime,
                screen=Screen.SETUP,
                selected_focus_minutes=selected,
                control_epoch=runtime.control_epoch + 1,
            )
        case CycleDuration():
            if runtime.screen is not Screen.SETUP:
                return runtime
            return replace(
                runtime,
                selected_focus_minutes=next_focus_minutes(
                    runtime.selected_focus_minutes, config.allowed_minutes
                ),
            )
        case BackHome():
            return replace(
                runtime,
                screen=Screen.HOME,
                control_epoch=runtime.control_epoch + 1,
            )
        case ShowTime():
            if now is None:
                raise ValueError("ShowTime requires a clock reading")
            return replace(
                runtime,
                clock_reveal_until_mono_ms=now.monotonic_ms + _CLOCK_REVEAL_MS,
            )


def context_for(screen: Screen, state: GameState) -> ControlContext:
    """Derive the binding context from screen and session status."""
    paused = (
        state.active_session is not None
        and state.active_session.status is SessionStatus.PAUSED
    )
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


def validate_bindings(
    bindings: ControlBindings,
    device_buttons: tuple[ButtonId, ...],
    max_buttons: int,
    actions: Mapping[ActionId, ActionDefinition] = ACTIONS,
) -> None:
    """Validate action references, device capabilities, layout and escape routes."""
    if not device_buttons or len(set(device_buttons)) != len(device_buttons):
        raise ValueError("device buttons must be nonempty and unique")
    if any(button <= 0 for button in device_buttons):
        raise ValueError("device button IDs must be positive")
    if len(device_buttons) > max_buttons:
        raise ValueError("device exposes more buttons than the UI layout supports")
    advertised = set(device_buttons)
    for (context, button, _gesture), action_id in bindings.items():
        if button not in advertised:
            raise ValueError(
                f"binding {context.value}/{button} references an unadvertised button"
            )
        if action_id not in actions:
            raise ValueError(f"binding references unknown action {action_id}")

    required_routes = {
        ControlContext.HOME: {ActionId.OPEN_SETUP, ActionId.OPEN_FEED},
        ControlContext.FEED: {
            ActionId.BUY_JOLLOF,
            ActionId.BUY_COFFEE,
            ActionId.BACK_HOME,
        },
        ControlContext.SETUP: {ActionId.CONFIRM_FOCUS, ActionId.BACK_HOME},
        ControlContext.FOCUS_RUNNING: {
            ActionId.END_CURRENT,
            ActionId.PAUSE_CURRENT,
        },
        ControlContext.FOCUS_PAUSED: {
            ActionId.END_CURRENT,
            ActionId.RESUME_CURRENT,
        },
        ControlContext.BREAK_OFFER: {
            ActionId.SKIP_BREAK,
            ActionId.START_BREAK,
        },
        ControlContext.BREAK_RUNNING: {
            ActionId.END_BREAK,
            ActionId.RESTART_FOCUS,
        },
    }
    for context, required in required_routes.items():
        configured = {
            action_id
            for (bound_context, _button, _gesture), action_id in bindings.items()
            if bound_context is context
        }
        missing = required - configured
        if missing:
            names = ", ".join(sorted(action.value for action in missing))
            raise ValueError(
                f"controls.{context.value} is missing required actions: {names}"
            )


def _label_for(
    context: ControlContext,
    button: ButtonId,
    state: GameState,
    bindings: ControlBindings,
    actions: Mapping[ActionId, ActionDefinition],
) -> ButtonLabel:
    press_action = _bound_action(context, button, Gesture.PRESS, bindings, actions)
    if press_action is not None:
        return ButtonLabel(
            button=button,
            label=press_action.label,
            enabled=press_action.available(state),
        )

    hold_action = _bound_action(context, button, Gesture.HOLD, bindings, actions)
    if hold_action is not None:
        return ButtonLabel(
            button=button, label=hold_action.label, enabled=hold_action.available(state)
        )

    return ButtonLabel(button=button, label=_UNBOUND_LABEL, enabled=False)


def _bound_action(
    context: ControlContext,
    button: ButtonId,
    gesture: Gesture,
    bindings: ControlBindings,
    actions: Mapping[ActionId, ActionDefinition],
) -> ActionDefinition | None:
    action_id = bindings.get((context, button, gesture))
    if action_id is None:
        return None
    return actions.get(action_id)
