# Components and hardware boundary

Status: inventory from the original notes; exact models and wiring are unconfirmed.

| Component | MVP role | Confirmation needed |
| --- | --- | --- |
| Laptop | Python rules/timers, local SQLite history, serial connection | OS and Python version |
| Raspberry Pi Pico-family board | MicroPython display/button peripheral over USB | Exact board, firmware and USB behavior |
| 1.8-inch LCD | Home pet/clock, setup, large countdown and button labels | Controller, resolution, bus, voltage, orientation and driver |
| Two 6 mm push buttons | Left/right press or hold | Pins, resistors, polarity and placement |
| USB data cable | Power and data | Match the actual connector; original USB-C note is unverified |
| Speaker/buzzer | Future optional sound | Type, drive circuit and pins; outside MVP |

The original “Pico / Pi Zero W” list was ambiguous. This plan assumes Pico;
Pi Zero would be a deliberate platform change. LCD versus OLED also needs hardware
confirmation. No hardware has been inspected or tested.

## Display and assets

Home: large central pet, clock at top right, labels above two bottom buttons.
Timer: large central countdown, small face at top right, bottom End/Pause labels.
Setup and break offer must fit their duration and both button labels without bars.

Two buttons are the baseline, not a hardcoded scanner limit. Define ID, GPIO and
label-layout slot per button in hardware_config.py. Iterate that table for scanning,
advertising capabilities and drawing label positions. Adding a third button needs
a real pin/placement check and a laptop binding, not new feeding/timer logic.
The post-MVP top XP/coin strip needs a layout pass alongside the clock/face;
it does not introduce numerical care stats or timer-progress artwork.

Provide full-body and small-face sprites for `calm`, `content`, `happy`, `sad`,
`focused` and `resting`; one `food_basic` sprite; and feeding/celebration frames.
Share animation frames where practical. A face must remain recognizable at its
small size. Exact pixel dimensions, fonts and palette depend on the confirmed LCD.

Firmware draws the laptop-selected mood, text, food and button labels. It may
debounce, animate and format seconds, but cannot calculate breaks, pause the game,
choose an emotion, interpret an action or track a hidden pet stat.

## Bring-up

Confirm electrical requirements and pinouts before wiring. Record the board and
driver here and put pins/orientation/debounce in `pico/hardware_config.py`.
Do not guess pins from these notes.

The application must own its USB stream: REPL, boot banners, IDE traffic and debug
printing must not contaminate messages. Confirm that arrangement on the selected
firmware. Keep button scanning and USB polling responsive while drawing.

Use a fake laptop device link and recorded screen examples during independent
development. The [serial protocol](serial_protocol.md) is the shared contract;
the display hardware stays behind `DisplayDriver`.
