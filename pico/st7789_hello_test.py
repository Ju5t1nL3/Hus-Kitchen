"""Adapted from russhughes' st7789_mpy examples/tiny_hello.py, using our own
DisplayDriver construction instead of their board-specific tft_config module.

Not part of the application -- one more independent cross-check reusing
their official example logic verbatim (random-colored "Hello!" text at
random positions, cycling all 4 rotations) against the exact same compiled
st7789 driver already wired into lcd_driver.py. Run via:

    python -m mpremote connect COM4 run pico/st7789_hello_test.py
"""

import random

import st7789
import utime
import vga1_8x8 as font
from hardware_config import DISPLAY_PINS
from lcd_driver import DisplayDriver

driver = DisplayDriver(DISPLAY_PINS)
tft = driver._display

tft.fill(st7789.RED)
length = len("Hello!")
tft.text(
    font,
    "Hello!",
    tft.width() // 2 - length // 2 * font.WIDTH,
    tft.height() // 2 - font.HEIGHT,
    st7789.WHITE,
    st7789.RED,
)
print(">>> LOOK NOW: RED screen with 'Hello!' centered")
utime.sleep(3)

for rotation in range(4):
    tft.rotation(rotation)
    tft.fill(st7789.BLACK)
    col_max = max(1, tft.width() - font.WIDTH * 6)
    row_max = max(1, tft.height() - font.HEIGHT)
    for _ in range(60):
        tft.text(
            font,
            "Hello!",
            random.randint(0, col_max),
            random.randint(0, row_max),
            st7789.color565(
                random.getrandbits(8), random.getrandbits(8), random.getrandbits(8)
            ),
            st7789.color565(
                random.getrandbits(8), random.getrandbits(8), random.getrandbits(8)
            ),
        )
    print(">>> LOOK NOW: rotation", rotation, "-- scattered 'Hello!' text")
    utime.sleep(2)

print("st7789 hello test complete")
