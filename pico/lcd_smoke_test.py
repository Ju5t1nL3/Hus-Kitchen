"""Transient on-device smoke test for lcd_driver.DisplayDriver.

Not part of the application; run directly via mpremote (see below), never
imported by main.py. Confirms the display initializes, the backlight turns
on, and blit_buffer draws real pixels -- independent of buttons/protocol.

    python -m mpremote connect COM4 run pico/lcd_smoke_test.py
"""

import time

from hardware_config import DISPLAY_PINS
from lcd_driver import DisplayDriver

RED = 0xF800
GREEN = 0x07E0
BLUE = 0x001F
WHITE_BYTES = b"\xff\xff"

print("constructing DisplayDriver (fills black on init)...")
driver = DisplayDriver(DISPLAY_PINS, fill_color=0x0000)
print(">>> LOOK NOW: should be BLACK")
time.sleep(3)

for name, color in (("RED", RED), ("GREEN", GREEN), ("BLUE", BLUE)):
    driver._display.fill(color)
    print(">>> LOOK NOW: should be", name)
    time.sleep(3)

square = WHITE_BYTES * (40 * 40)
driver.draw_region((10, 10, 40, 40), square)
print(">>> LOOK NOW: should be BLUE with a WHITE 40x40 square near top-left")
time.sleep(3)

print("test complete")
