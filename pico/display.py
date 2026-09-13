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

# Confirmed 128x160 panel (../pico/README.md). Provisional text layout until
# M16 finalizes real sprite positions/pixel art; only affects where text
# draws relative to the (currently blank) pet/background region.
_SCREEN_WIDTH = 128
_SCREEN_HEIGHT = 160
_CLOCK_SIZE = "normal"  # vga1_8x16, see lcd_driver.py
_CLOCK_CHAR_WIDTH = 8
_TIMER_SIZE = "large"  # vga1_bold_16x32, see lcd_driver.py
_TIMER_CHAR_WIDTH = 16
_LABEL_SIZE = "normal"
_LABEL_CHAR_WIDTH = 8
_MARGIN = 4


class NullDisplayDriver:
    """Placeholder DisplayDriver until M16 wires the real ST7735S driver."""

    def draw_region(self, rect, pixels):
        del rect, pixels

    def draw_text(self, x, y, text, size):
        del x, y, text, size


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
        self._draw_text()

    def _draw_text(self):
        """Draw whatever text fields the current view carries, as given.

        Only formats raw seconds into `MM:SS` -- everything else (whether
        clock_text/timer_seconds are present at all, what a label says) is
        already decided by the laptop; firmware never infers screen/mood-
        based drawing choices of its own.
        """
        if not self.connected or self.view is None:
            return
        view = self.view

        clock_text = view.get("clock_text")
        if clock_text is not None:
            x = _SCREEN_WIDTH - len(clock_text) * _CLOCK_CHAR_WIDTH - _MARGIN
            self._driver.draw_text(x, _MARGIN, clock_text, _CLOCK_SIZE)

        timer_seconds = view.get("timer_seconds")
        if timer_seconds is not None:
            timer_text = "%d:%02d" % (timer_seconds // 60, timer_seconds % 60)
            width = len(timer_text) * _TIMER_CHAR_WIDTH
            x = (_SCREEN_WIDTH - width) // 2
            y = (_SCREEN_HEIGHT - 32) // 2
            self._driver.draw_text(x, y, timer_text, _TIMER_SIZE)

        buttons = view.get("buttons") or ()
        y = _SCREEN_HEIGHT - 16 - _MARGIN
        count = len(buttons)
        for index, entry in enumerate(buttons):
            label = entry["label"]
            width = len(label) * _LABEL_CHAR_WIDTH
            if count == 1:
                x = (_SCREEN_WIDTH - width) // 2
            elif index == 0:
                x = _MARGIN
            elif index == count - 1:
                x = _SCREEN_WIDTH - width - _MARGIN
            else:
                x = (_SCREEN_WIDTH - width) // 2
            self._driver.draw_text(x, y, label, _LABEL_SIZE)
