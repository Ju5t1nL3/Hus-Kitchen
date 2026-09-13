"""ST7735S display driver adapter for `display.Renderer`.

Wraps russhughes' `st7789` C driver module (repo name `st7789_mpy`; the same
compiled module supports ST7735/ST7789/ILI9341-family panels via its init
table -- see ../pico/README.md). Exposes `draw_region(rect, pixels)` and
`draw_text(x, y, text, size)`, the same calls `Renderer` already makes
against `NullDisplayDriver`, so swapping drivers in `main.py` requires no
change above this module.

Requires a board reflashed with a russhughes st7789_mpy build (precompiled
RP2040 firmware, or built from source) so that `import st7789` resolves to
the compiled module rather than stock MicroPython -- see MICROPYTHON_VERSION
and ../pico/README.md before relying on this. `vga1_8x16`/`vga1_bold_16x32`
are already frozen into that firmware; the copies in this folder are for
review/tracking, not required on-device.

Physical bring-up is currently BLOCKED on an unreliable SPI connection, not
wiring/config/driver correctness -- see ../pico/README.md's display bring-up
section before spending more time on pin/mode/driver changes. `draw_region`
still has nothing real to blit until M16 supplies sprite pixel data; the text
path drawn here is real (uses the driver's own bitmap-font `text()` call)
but is unverified on hardware for the same reason.
"""

import machine
import st7789
import vga1_8x16
import vga1_bold_16x32

_FONTS = {
    "normal": vga1_8x16,
    "large": vga1_bold_16x32,
}


class DisplayDriver:
    """Real ST7735S driver behind the same interface as NullDisplayDriver."""

    def __init__(self, pins, fill_color=0x0000):
        spi = machine.SPI(
            pins["spi_id"],
            baudrate=pins["baudrate"],
            polarity=0,
            phase=0,
            sck=machine.Pin(pins["sck"]),
            mosi=machine.Pin(pins["mosi"]),
        )
        self._display = st7789.ST7789(
            spi,
            pins["width"],
            pins["height"],
            reset=machine.Pin(pins["reset"], machine.Pin.OUT),
            dc=machine.Pin(pins["dc"], machine.Pin.OUT),
            cs=machine.Pin(pins["cs"], machine.Pin.OUT),
            backlight=machine.Pin(pins["backlight"], machine.Pin.OUT),
            rotation=pins["rotation"],
            color_order=st7789.RGB,
            inversion=False,
        )
        self._width = pins["width"]
        self._height = pins["height"]
        self._display.init()
        self._display.on()
        self._display.fill(fill_color)

    def draw_region(self, rect, pixels):
        """(x, y, w, h) + RGB565 bytes -> blit; `None` pixels is a no-op.

        `rect=None` with real `pixels` means "whole screen"; until M16
        supplies actual sprite/layout pixel data, `pixels` stays `None` and
        nothing is blitted beyond the constructor's initial fill.
        """
        if pixels is None:
            return
        if rect is None:
            x, y, w, h = 0, 0, self._width, self._height
        else:
            x, y, w, h = rect
        self._display.blit_buffer(pixels, x, y, w, h)

    def draw_text(self, x, y, text, size):
        """Draw `text` at (x, y) using the bitmap font for `size` ("normal"
        or "large"), white on black -- see ../pico/vga1_8x16.py and
        vga1_bold_16x32.py, both frozen into the flashed RP2 firmware.
        """
        self._display.text(_FONTS[size], text, x, y, st7789.WHITE, st7789.BLACK)
