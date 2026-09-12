"""Button label resolution (the read-only slice of M11 that M12 depends on).

Full M11 still owns: startup validation of bindings (unknown actions, duplicate
(context, button, gesture) entries, unadvertised IDs, layouts that do not fit),
controls.resolve for turning a gesture into a ControlIntent, and controls.navigate
for Home/setup selection. This module only derives what the presenter needs to
render button labels, per docs/class_design.md's "Adding or changing buttons"
section: the press action supplies the primary label; if only hold is bound,
show its label as a hold hint; an unbound button shows a disabled dash.
"""

from deskpet.core.commands import ActionId
from deskpet.core.models import ButtonId, GameState, Gesture
from deskpet.core.views import (
    ActionDefinition,
    ButtonLabel,
    ControlBindings,
    ControlContext,
)

_UNBOUND_LABEL = "—"


def labels(
    context: ControlContext,
    state: GameState,
    device_buttons: tuple[ButtonId, ...],
    bindings: ControlBindings,
    actions: dict[ActionId, ActionDefinition],
) -> tuple[ButtonLabel, ...]:
    """Derive one label per advertised button for the given control context."""
    return tuple(
        _label_for(context, button, state, bindings, actions)
        for button in device_buttons
    )


def _label_for(
    context: ControlContext,
    button: ButtonId,
    state: GameState,
    bindings: ControlBindings,
    actions: dict[ActionId, ActionDefinition],
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
    actions: dict[ActionId, ActionDefinition],
) -> ActionDefinition | None:
    action_id = bindings.get((context, button, gesture))
    if action_id is None:
        return None
    return actions.get(action_id)
