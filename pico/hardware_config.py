"""Pico hardware wiring: GPIO pins, debounce/hold timing and button layout.

Confirmed hardware (see ../pico/README.md): RP2040 Raspberry Pi Pico (non-W).
Button pins and active-low/pull-up polarity were confirmed on-device by
scanning GPIO0-22/26-28 for a live button press: GPIO10 and GPIO11 showed
clean high-low-high transitions on press (docs previously said GPIO14/15,
which were verified idle-high but never toggled -- corrected here).

Display bus pins below reflect the actual physical wiring for the 128x160
ST7735S SPI display (SCK/MOSI on SPI0's hardware pins; CS/DC/RESET/backlight
are plain GPIO outputs, no alternate-function constraint). An initial pin
assignment guessed DC/RESET swapped and backlight on the wrong GPIO entirely
(GP22 instead of GP16); corrected here after an on-device smoke test showed a
persistently white, unresponsive panel -- see ../pico/README.md for the
smoke-test method and outstanding verification.
"""

DEBOUNCE_MS = 20
HOLD_MS = 600

# One entry per physical button: id (advertised over the wire, layout order),
# gpio, active_low/pull (confirmed on-device, see module docstring) and a
# layout slot for future label placement. Add a row here (plus a `ready`
# advertisement and a laptop binding) to add a physical button.
BUTTONS = (
    {"id": 1, "gpio": 10, "active_low": True, "pull": "up", "slot": "left"},
    {"id": 2, "gpio": 11, "active_low": True, "pull": "up", "slot": "right"},
)

# RP2040 SPI0 bus pins for the 128x160 ST7735S display, via russhughes'
# st7789_mpy driver (built with custom ST7735 init support). PROPOSED, not
# yet verified on real wiring -- see module docstring.
DISPLAY_PINS = {
    "spi_id": 0,
    "sck": 18,
    "mosi": 19,
    "dc": 21,
    "reset": 20,
    # diagnostic: moved off GP17 (physical pin 22) to GP22 (physical pin 29)
    # after GP17-controlled CS produced nothing while CS-tied-to-GND produced
    # visible (if unsynced) noise -- suspected bad GP17 pin/row.
    "cs": 22,
    "backlight": 16,
    "baudrate": 2_000_000,
    "width": 128,
    "height": 160,
    "rotation": 0,
}
