# Components and hardware boundary

Status: inventory from the original notes; exact models and wiring are unconfirmed.

| Component | MVP role | Confirmation needed |
| --- | --- | --- |
| Laptop | Python application, rules, timer, SQLite, serial connection | Supported OS and Python version |
| Raspberry Pi Pico-family board | MicroPython display/button peripheral over USB | Exact board, installed firmware, USB serial behavior |
| 1.8-inch LCD | Pet, clock, timer, menu | Controller, resolution, bus, voltage, driver and orientation |
| Two 6 mm push buttons; optional third | Raw press/hold input | GPIO pins, pull resistors, wiring polarity |
| USB data cable | Power and data | Connector must match actual board; original USB-C note is unverified |
| Speaker/buzzer | Future sound feedback | Device type, drive circuit and pins; outside MVP |

The original list said “Pico / Pi Zero W.” This plan selects a Pico as a design
assumption. A Pi Zero is a different platform and should be a deliberate hardware
decision. No hardware has been inspected or tested. The original future notes
also said OLED; this plan uses the listed LCD and hides its details behind
`DisplayDriver`.

## Firmware responsibilities

- Read and debounce GPIO buttons; report physical button number and gesture.
- Parse bounded newline-delimited JSON and apply complete render snapshots.
- Draw sprites, text, menus and laptop-selected progress stages.
- Play requested animations; service USB and buttons while animating.
- Report readiness, respond to pings, and show a connection overlay if stale.

Firmware does not know food prices, reward rules, focus duration, local time zone,
what a button means in a mode, or whether a session succeeded. Prices, clock text,
selected actions, and enabled states arrive in render snapshots.

## Bring-up checklist

Before wiring, identify the board and display and consult their actual pinouts and
electrical requirements. Put confirmed choices in `pico/hardware_config.py` when
implementation starts; record model/driver references here. Do not invent pin
assignments from the current notes.

Verify the USB stream can run the protocol without REPL, boot banners, `print()`
debugging, or concurrent IDE access contaminating it. Use a dedicated data channel
if supported by the selected firmware, or arrange for the application to own its
stream. This remains a hardware bring-up task.

The laptop can use `FakeDeviceLink`; firmware can use recorded protocol fixtures.
Neither team's core work needs to wait for final wiring. See
[serial_protocol.md](serial_protocol.md).
