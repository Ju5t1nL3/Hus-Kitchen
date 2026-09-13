"""One-off diagnostic: logic-probe test for RST, reusing GP14 as the probe.
Requires a jumper wire tapped directly at the display board's own RST pin,
branching to GP14 (physical pin 19).

Not part of the application. Run via:
    python -m mpremote connect COM4 run pico/wire_probe_test.py
"""

import time

import machine
from hardware_config import DISPLAY_PINS

rst_out = machine.Pin(DISPLAY_PINS["reset"], machine.Pin.OUT)
rst_probe = machine.Pin(14, machine.Pin.IN, machine.Pin.PULL_DOWN)

rst_out.value(0)
time.sleep_ms(50)

rst_seen_high = False
rst_seen_low_after_high = False

print("--- driving RST high/low ---")
for i in range(10):
    rst_out.value(1)
    time.sleep_ms(20)
    r = rst_probe.value()
    print("RST=1: rst_probe=%d" % r)
    if r:
        rst_seen_high = True

    rst_out.value(0)
    time.sleep_ms(20)
    r = rst_probe.value()
    print("RST=0: rst_probe=%d" % r)
    if rst_seen_high and not r:
        rst_seen_low_after_high = True

print()
print("RST toggled cleanly (high then low seen at probe):", rst_seen_low_after_high)
