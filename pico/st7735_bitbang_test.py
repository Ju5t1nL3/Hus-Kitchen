"""One-off diagnostic: drive boochow's ST7735 driver over a manual,
software-clocked (bit-banged) SPI instead of the RP2040 hardware SPI
peripheral, at a very low, generous-delay clock rate.

Not part of the application. Purpose: hardware SPI failed identically across
2 drivers, 4 clock modes and both baud rates tried so far, but the physical
connection has shown signs of being marginal (one-off noise on the CS-to-GND
test that didn't reproduce). A slow, manually-clocked signal is far more
tolerant of a flaky/marginal wire or breadboard contact than fast hardware
SPI -- if THIS works, it confirms a signal-integrity/connection-quality
problem rather than a fully dead line. Run via:

    python -m mpremote connect COM4 run pico/st7735_bitbang_test.py
"""

import time

import machine
from hardware_config import DISPLAY_PINS
from ST7735 import TFT


class BitBangSPI:
    """Minimal software SPI, mode 0, with a generous per-bit delay."""

    def __init__(self, sck_gpio, mosi_gpio, delay_us=20):
        self._sck = machine.Pin(sck_gpio, machine.Pin.OUT)
        self._mosi = machine.Pin(mosi_gpio, machine.Pin.OUT)
        self._delay = delay_us
        self._sck.value(0)

    def write(self, buf):
        for byte in buf:
            for bit_index in range(7, -1, -1):
                self._mosi.value((byte >> bit_index) & 1)
                time.sleep_us(self._delay)
                self._sck.value(1)
                time.sleep_us(self._delay)
                self._sck.value(0)
                time.sleep_us(self._delay)


spi = BitBangSPI(DISPLAY_PINS["sck"], DISPLAY_PINS["mosi"], delay_us=20)
bl = machine.Pin(DISPLAY_PINS["backlight"], machine.Pin.OUT)
bl.value(1)

tft = TFT(spi, DISPLAY_PINS["dc"], DISPLAY_PINS["reset"], DISPLAY_PINS["cs"])
print(">>> initr() over bit-banged SPI...")
tft.initr()

print(">>> LOOK NOW: fill BLACK")
tft.fill(TFT.BLACK)
time.sleep(3)

print(">>> LOOK NOW: fill RED")
tft.fill(TFT.RED)
time.sleep(3)

print(">>> LOOK NOW: fill GREEN")
tft.fill(TFT.GREEN)
time.sleep(3)

print("bit-bang test complete")
