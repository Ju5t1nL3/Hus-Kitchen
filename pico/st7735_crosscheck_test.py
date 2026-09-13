"""One-off cross-check: boochow's pure-Python ST7735 driver, same wiring.

Diagnostic only -- not part of the application, not wired into lcd_driver.py.
If this ALSO shows nothing on the panel, that's strong evidence the problem
is electrical/hardware rather than the russhughes st7789_mpy driver. Run via:

    python -m mpremote connect COM4 run pico/st7735_crosscheck_test.py
"""

import time

import machine
from hardware_config import DISPLAY_PINS
from ST7735 import TFT

spi = machine.SPI(
    DISPLAY_PINS["spi_id"],
    baudrate=DISPLAY_PINS["baudrate"],
    polarity=0,
    phase=0,
    sck=machine.Pin(DISPLAY_PINS["sck"]),
    mosi=machine.Pin(DISPLAY_PINS["mosi"]),
)

tft = TFT(spi, DISPLAY_PINS["dc"], DISPLAY_PINS["reset"], DISPLAY_PINS["cs"])
print(">>> initr() -- red-tab init sequence...")
tft.initr()

print(">>> LOOK NOW: fill BLACK")
tft.fill(TFT.BLACK)
time.sleep(2)

print(">>> LOOK NOW: fill RED")
tft.fill(TFT.RED)
time.sleep(2)

print(">>> LOOK NOW: fill GREEN")
tft.fill(TFT.GREEN)
time.sleep(2)

print(">>> LOOK NOW: fill BLUE")
tft.fill(TFT.BLUE)
time.sleep(2)

print("cross-check test complete")
