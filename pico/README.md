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

Record wiring compactly:

| Logical component | Board pin/GPIO | Direction | Pull/polarity or bus role | Verified |
| --- | --- | --- | --- | --- |
| Button 1 | TBD | Input | TBD | No |
| Button 2 | TBD | Input | TBD | No |
| Display | TBD | Output/bus | TBD | No |

This is a project-relevant inventory, not a board encyclopedia. Omit peripherals
the desk pet will never use, but do not omit a capability on which the display,
buttons, USB protocol, timing, assets or likely sound expansion depends.

## 2. Choose and pin MicroPython

1. Find the official MicroPython download for the exact board—not merely a board
   with a similar name.
2. Choose a stable release compatible with the display driver and modules above.
3. Flash it and smoke-test USB serial, both buttons, the display, timing and JSON.
4. Replace `UNPINNED` in `MICROPYTHON_VERSION` with the exact release/build.
5. Fill in the record below so another teammate can reproduce the setup.

| Firmware fact | Verified value |
| --- | --- |
| Board download page | TBD |
| MicroPython release/build | TBD |
| UF2 filename | TBD |
| UF2 checksum | TBD |
| Test date | TBD |
| Smoke-test result | TBD |

Do not assume that an `RPI_PICO` UF2 is valid for another Pico-family board.

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

## Firmware boundaries

Firmware may scan/debounce buttons, parse bounded messages, draw screens and run
requested animations. It must not decide timer outcomes, emotions, rewards or
persistence. See [components](../docs/components.md), the
[serial protocol](../docs/serial_protocol.md), and [M01/M15–M17](../docs/todo.md)
before changing hardware or firmware.
