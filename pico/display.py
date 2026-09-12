"""Desk-pet view state, connection overlay and bounded animation playback.

`Renderer` owns exactly what the spec allows firmware to know: the last
validated view, connection status and a bounded, best-effort animation
queue. It never infers mood, formats anything beyond seconds, or decides
what to draw beyond the laptop-selected screen/mood -- see
../docs/serial_protocol.md and ../docs/class_design.md.

The real ST7735S SPI driver is M16's job, once ../pico/README.md's display
bus pins are confirmed. `NullDisplayDriver` keeps `FirmwareApp` runnable
end-to-end without it; swap it for `lcd_driver.DisplayDriver` behind the
same `draw_region` call and nothing above this module changes.
"""

_ANIMATION_QUEUE_LIMIT = 32


class NullDisplayDriver:
    """Placeholder DisplayDriver until M16 wires the real ST7735S driver."""

    def draw_region(self, rect, pixels):
        del rect, pixels


class Renderer:
    """Atomic desired-view swap, connection overlay and animation playback."""

    def __init__(self, driver):
        self._driver = driver
        self.view = None
        self.connected = False
        self._animation_queue = []
        self._recent_animation_ids = []
        self._dirty = False

    def set_view(self, view):
        """Valid complete view -> atomic desired-view swap and dirty marking."""
        self.view = view
        self._dirty = True

    def enqueue_animation(self, animation_id, name, food_sprite):
        """Valid cue -> bounded, compatible visual playback only."""
        del food_sprite
        if animation_id in self._recent_animation_ids:
            return
        self._recent_animation_ids.append(animation_id)
        if len(self._recent_animation_ids) > _ANIMATION_QUEUE_LIMIT:
            self._recent_animation_ids.pop(0)
        if len(self._animation_queue) >= _ANIMATION_QUEUE_LIMIT:
            self._animation_queue.pop(0)
        self._animation_queue.append({"animation_id": animation_id, "name": name})
        self._dirty = True

    def set_connected(self, value):
        """Boolean -> connection overlay and stale-animation clearing."""
        if value == self.connected:
            return
        self.connected = value
        if not value:
            self._animation_queue = []
            self.view = None
        self._dirty = True

    def tick(self, now_ms):
        """Firmware ticks -> bounded drawing/animation work; no game countdown."""
        del now_ms
        if not self._dirty:
            return
        self._dirty = False
        # Full-screen redraw until M16 supplies real layouts/sprites and
        # partial dirty-region tracking; `None` stands in for "whole screen".
        self._driver.draw_region(None, None)
