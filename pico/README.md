# Pico firmware

This folder contains the MicroPython program for the physical device. It reads
and debounces buttons, validates USB messages, draws laptop-provided views and
plays requested animations. Timer, emotion and reward decisions stay on the laptop.

MicroPython is a separate runtime from laptop CPython. Complete M01 in the order
below before relying on a particular firmware version or language feature.

## 1. Report the existing board and its relevant capabilities

Inspect the working breadboard first. Record facts and test results here rather
than rebuilding it or guessing from a generic Pico guide. Cover every item that
can affect this project:

| Area | What to identify or verify |
| --- | --- |
| Board | Exact model/variant, MCU (such as RP2040 or RP2350) and board revision |
| Memory/storage | Flash and RAM capacity, plus usable filesystem space |
| USB | An HP Windows laptop can detect/program the Pico and control its LEDs over the confirmed data cable; still record the connector, CDC/serial behavior, device name/IDs and whether the application shares the REPL stream |
| Power | Normal power source and voltage requirements |
| GPIO | Every used pin, its direction, voltage level and connected component |
| Buttons | Logical ID, GPIO, active-high/low, internal/external pull and observed debounce behavior |
| Display | Module, controller, resolution, color depth, orientation and voltage |
| Display bus | SPI/I2C/parallel bus, bus number/frequency, and all data/control pins |
| Display driver | Source, version/commit, license, required APIs and a tested screen/drawing operation |
| Drawing | `framebuf` or other API, framebuffer memory use and full/partial redraw behavior |
| Time | Availability and behavior of `ticks_ms()` and `ticks_diff()` across wraparound |
| Protocol data | Available `json`/`ujson`, UTF-8/newline handling and support for the 2,048-byte line limit |
| Files/boot | Roles of `boot.py` and `main.py`, how code/assets are copied, and remaining filesystem space |
| Reset/recovery | Reset cause, watchdog availability if used, and recovery/reflash procedure |
| Scheduling | Whether one cooperative loop is sufficient; the MVP does not require threads or asyncio |
| Expansion | PWM/audio pins, interrupts, PIO or DMA only if planned hardware will require them |
| Networking | Whether the board has Wi-Fi; the MVP does not use it and future HTTP services stay laptop-side |
| Existing work | What already works, what was tested, and what remains unfinished |

Known bring-up result: an HP Windows laptop successfully communicated with the
Pico sufficiently to program it and control its LEDs. This confirms the board,
cable and host can communicate, but does not yet demonstrate that the desk-pet
application can exchange clean `READY`/`PING`/`PONG` messages in both directions.

Board and MCU: Raspberry Pi Pico (non-W variant), RP2040.

Firmware already on the board: MicroPython v1.24.0, confirmed via
`sys.implementation`/`sys.version` in a Thonny REPL session.

USB: the board enumerates on Windows as a CDC serial device, VID `2E8A`
(Raspberry Pi Foundation), PID `0005`, at `COM6` on the current test laptop. This
PID is the standard MicroPython REPL/CDC identity, matching the already-flashed
v1.24.0. Still to confirm: connector type, and whether the desk-pet app's
newline-delimited protocol stays clean alongside REPL traffic once `main.py`
runs the application loop instead of Thonny's interactive session.

Display: 1.8-inch SPI TFT LCD, 128x160 resolution, full color, ST7735S
controller. Bus pins (SCK/MOSI/CS/DC/RST/backlight) are not yet assigned —
confirm and record before implementing `lcd_driver.py`.

Record wiring compactly:

| Logical component | Board pin/GPIO | Direction | Pull/polarity or bus role | Verified |
| --- | --- | --- | --- | --- |
| Button 1 (left) | GPIO10 | Input | Active-low, internal pull-up | Yes |
| Button 2 (right) | GPIO11 | Input | Active-low, internal pull-up | Yes |
| Display | TBD (SPI bus) | Output/bus | ST7735S, 128x160, SPI | No |

This is a project-relevant inventory, not a board encyclopedia. Omit peripherals
the desk pet will never use, but do not omit a capability on which the display,
buttons, USB protocol, timing, assets or likely sound expansion depends.

Buttons: confirmed on-device by scanning GPIO0-22/26-28 (excluding GPIO2,
already driving a confirmed test LED) with internal pull-ups while pressing
each button. Button 1 (left) is GPIO10, button 2 (right) is GPIO11; both are
active-low with a clean high-low-high transition on press, so an internal
pull-up needs no external resistor. (Docs previously said GPIO14/GPIO15;
those pins never toggled on press and were corrected here.)

End-to-end verified: `main.py`'s `ButtonScanner` (via `buttons.py` and the
corrected `hardware_config.py`) reports a clean `press` gesture for each
physical tap of both buttons, confirmed visually with the already-wired
GPIO2 LED blinking on every detected gesture.

## 2. Choose and pin MicroPython

1. Find the official MicroPython download for the exact board—not merely a board
   with a similar name.
2. Choose a stable release compatible with the display driver and modules above.
3. Flash it and smoke-test USB serial, both buttons, the display, timing and JSON.
4. Replace `UNPINNED` in `MICROPYTHON_VERSION` with the exact release/build.
5. Fill in the record below so another teammate can reproduce the setup.

| Firmware fact | Verified value |
| --- | --- |
| Board download page | https://micropython.org/download/RPI_PICO/ |
| MicroPython release/build | v1.24.0 (already flashed; not reflashed as part of this pass) |
| UF2 filename | `RPI_PICO-20241025-v1.24.0.uf2` |
| UF2 checksum | TBD — compute locally (`sha256sum`/`Get-FileHash`) if/when the board is reflashed with a downloaded copy of this UF2 |
| Test date | TBD — record when the smoke test below is actually run |
| Smoke-test result | TBD — USB serial, both buttons, display, timing and JSON not yet smoke-tested against this exact build |

Do not assume that an `RPI_PICO` UF2 is valid for another Pico-family board.
Since v1.24.0 is already running and was not reflashed here, its checksum was
not independently computed; verify it against the official download page if a
fresh reflash is ever needed.

## 3. Align and verify Ruff

`pico/ruff.toml` is deliberately provisional. After pinning MicroPython:

1. Check which Python syntax that firmware build actually supports.
2. Set Ruff's `target-version` to the closest conservative CPython syntax floor.
3. Keep MicroPython-only imports such as `machine` from being incorrectly treated
   as desktop dependencies.
4. Run formatting/lint checks from `laptop/`, reusing its locked Ruff installation:

```sh
uv run ruff format --check --config ../pico/ruff.toml ../pico
uv run ruff check --config ../pico/ruff.toml ../pico
```

Ruff's target is a syntax/lint setting, not a MicroPython version selector. It
cannot validate firmware-only APIs or prove runtime compatibility; the smoke test
on the actual board is the final check.

## Performance record

Complete this during real-device acceptance task M21. Use both an ordinary timer
render and the largest valid shared fixture. Measure before considering a custom
plaintext or binary protocol.

| Scenario | Line bytes | Decode + validation | Display update | Free-memory change | Button → render |
| --- | --- | --- | --- | --- | --- |
| Timer render | TBD | TBD | TBD | TBD | TBD |
| Largest valid fixture | TBD | TBD | TBD | TBD | TBD |

Also note any garbage-collection pause or growing memory use observed during
repeated one-second timer updates, and identify the measured bottleneck.

## Firmware boundaries

Firmware may scan/debounce buttons, parse bounded messages, draw screens and run
requested animations from locally stored sprites/frames. It must not decide timer
outcomes, emotions, rewards or persistence. See [components](../docs/components.md), the
[serial protocol](../docs/serial_protocol.md), and [M01/M15–M17](../docs/todo.md)
before changing hardware or firmware.
