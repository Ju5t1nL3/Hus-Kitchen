"""Pure decisions for explicit, independently controlled tracking consent."""

from deskpet.core.commands import Accepted, Decision, Rejected
from deskpet.core.events import EventSource, TrackingPreferencesChanged
from deskpet.core.models import GameState, RejectionCode


def decide_toggle(
    state: GameState,
    selected_row: int,
    operation_key: str,
    *,
    camera_available: bool,
) -> Decision:
    """Toggle one settings row, rejecting unavailable integrations."""
    if state.active_session is not None or state.pending_break is not None:
        return Rejected(RejectionCode.UNAVAILABLE)
    if selected_row == 0:
        keyboard_enabled = not state.keyboard_tracking_enabled
        camera_enabled = state.camera_tracking_enabled
    elif selected_row == 1:
        if not camera_available and not state.camera_tracking_enabled:
            return Rejected(RejectionCode.UNAVAILABLE)
        keyboard_enabled = state.keyboard_tracking_enabled
        camera_enabled = not state.camera_tracking_enabled
    else:
        raise ValueError("selected_row must select keyboard or camera")
    return Accepted(
        TrackingPreferencesChanged(
            source=EventSource.LOCAL_CONTROLS,
            dedupe_key=operation_key,
            keyboard_enabled=keyboard_enabled,
            camera_enabled=camera_enabled,
        )
    )
