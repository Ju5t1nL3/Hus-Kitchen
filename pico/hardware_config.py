"""Pico hardware wiring: GPIO pins, debounce/hold timing and button layout.

Confirmed hardware (see ../pico/README.md): RP2040 Raspberry Pi Pico (non-W).
Button pins and active-low/pull-up polarity were confirmed on-device by
scanning GPIO0-22/26-28 for a live button press: GPIO10 and GPIO11 showed
clean high-low-high transitions on press (docs previously said GPIO14/15,
which were verified idle-high but never toggled -- corrected here). Display
bus pins remain unassigned until M16 confirms wiring for the 128x160 ST7735S
SPI display.
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

# Bus pins TBD until M16 confirms wiring for the 128x160 ST7735S SPI display.
DISPLAY_PINS = None
