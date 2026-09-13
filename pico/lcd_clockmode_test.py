"""Transient on-device test cycling all 4 SPI clock modes back-to-back.

Not part of the application. Constructs a fresh SPI bus + ST7789 driver
instance for each (polarity, phase) combination and fills black then red,
pausing so a human can watch continuously across all four without needing
a redeploy between each. Run via:

    python -m mpremote connect COM4 run pico/lcd_clockmode_test.py
"""

import time

import machine
import st7789
from hardware_config import DISPLAY_PINS

MODES = ((0, 0), (0, 1), (1, 0), (1, 1))

for polarity, phase in MODES:
    print(f">>> MODE polarity={polarity} phase={phase}: constructing...")
    spi = machine.SPI(
        DISPLAY_PINS["spi_id"],
        baudrate=DISPLAY_PINS["baudrate"],
        polarity=polarity,
        phase=phase,
        sck=machine.Pin(DISPLAY_PINS["sck"]),
        mosi=machine.Pin(DISPLAY_PINS["mosi"]),
    )
    display = st7789.ST7789(
        spi,
        DISPLAY_PINS["width"],
        DISPLAY_PINS["height"],
        reset=machine.Pin(DISPLAY_PINS["reset"], machine.Pin.OUT),
        dc=machine.Pin(DISPLAY_PINS["dc"], machine.Pin.OUT),
        cs=machine.Pin(DISPLAY_PINS["cs"], machine.Pin.OUT),
        backlight=machine.Pin(DISPLAY_PINS["backlight"], machine.Pin.OUT),
        rotation=DISPLAY_PINS["rotation"],
        color_order=st7789.RGB,
        inversion=False,
    )
    display.init()
    display.on()
    display.fill(0x0000)
    print(f">>> MODE polarity={polarity} phase={phase}: LOOK NOW, should be BLACK")
    time.sleep(2)
    display.fill(0xF800)
    print(f">>> MODE polarity={polarity} phase={phase}: LOOK NOW, should be RED")
    time.sleep(2)
    spi.deinit()

print("all 4 clock modes tried")
