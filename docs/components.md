# Components and hardware boundary

Status: the user reports some board setup is already done. The exact completed
steps, models and wiring are not yet recorded in these docs. Inspect and document
that setup under M01 in [todo.md](todo.md) before repeating or replacing work.

| Component | MVP role | Confirmation needed |
| --- | --- | --- |
| Laptop | CPython 3.14.6 rules/timers, local SQLite history, serial connection | HP Windows laptop has detected/programmed the Pico and controlled its LEDs; clean application serial messaging remains to be tested |
| Raspberry Pi Pico-family board | MicroPython display/button peripheral over USB | RP2040 confirmed; exact board variant (Pico vs Pico W), firmware release and USB CDC behavior beyond enumeration still TBD |
| 1.8-inch LCD | Home pet/clock, setup, large countdown and button labels | ST7735S controller, 128x160, full color, SPI bus confirmed; bus pins, voltage and orientation still TBD |
| Two 6 mm push buttons | Left/right press or hold | Button 1 on GPIO14, Button 2 on GPIO15 confirmed; pull direction/polarity and placement still TBD |
| USB data cable | Power and data | Confirmed on an HP Windows laptop by programming the Pico and controlling its LEDs; connector type is not yet recorded |
| Speaker/buzzer | Future optional sound | Type, drive circuit and pins; outside MVP |

The original “Pico / Pi Zero W” list was ambiguous. This plan assumes Pico;
Pi Zero would be a deliberate platform change. LCD versus OLED also needs hardware
confirmation in these docs. This documentation pass has not independently inspected
or tested the hardware; it does not imply the team has done no setup or testing.

The expected deployment host is currently an HP Windows laptop. Keep laptop code
OS-agnostic: discover/configure the serial port rather than hardcoding a Windows
`COM` name, and isolate OS-specific behavior behind adapters if it becomes necessary.

## Display and assets

Home: large central pet, clock at top right, and three bottom button slots (the
unbound third slot is disabled). Timer: large central countdown, small face at top
right, and three action labels. Setup and break offer must fit all three labels
without bars.

Three buttons are the MVP baseline, not a hardcoded scanner limit. Define ID, GPIO
and label-layout slot per button in hardware_config.py. Iterate that table for
scanning, advertising capabilities and drawing label positions. Adding or removing
a button needs a real pin/placement check and a laptop binding, not new feeding or
timer logic.
The XP/level/yarn strip needs a layout pass alongside the clock/face;
it does not introduce numerical care stats or timer-progress artwork.

Provide full-body and small-face sprites for `calm`, `content`, `happy`, `sad`,
`focused` and `resting`; one `food_basic` sprite; and feeding/celebration frames.
Share animation frames where practical. A face must remain recognizable at its
small size. Exact pixel dimensions, fonts and palette depend on the confirmed LCD.

Keep source frames as individual PNG files, including two-frame animations. A
small asset manifest groups each animation ID with its ordered filenames and frame
timing so ordering does not depend on directory listings or filename guessing.
Convert those PNG sources into Pico-friendly bitmap data before deployment; the
firmware does not decode PNG files or receive frames over USB at runtime.

Firmware draws the laptop-selected mood, text, food and button labels. It may
debounce, animate and format seconds, but cannot calculate breaks, pause the game,
choose an emotion, interpret an action or track a hidden pet stat.

## Bring-up

Follow the ordered inventory, firmware-selection and Ruff-alignment checklist in
the [Pico README](../pico/README.md). Record stable hardware facts here; keep the
reproducible firmware record and detailed wiring table with the firmware. Confirm
electrical requirements before any new wiring. Put confirmed pins, orientation
and debounce settings in `pico/hardware_config.py`.
Do not guess pins from these notes.

Basic laptop-to-Pico programming/control is confirmed on Windows. The application
must still prove its bidirectional newline-delimited serial exchange: REPL, boot
banners, IDE traffic and debug printing must not contaminate messages. Confirm that
arrangement on the selected firmware. Keep button scanning and USB polling responsive
while drawing.

Use a fake laptop device link and recorded screen examples during independent
development. The [serial protocol](serial_protocol.md) is the shared contract;
the display hardware stays behind `DisplayDriver`.
