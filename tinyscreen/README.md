# TinyScreen+ firmware and hardware record

This folder contains the C++/Arduino program for the physical device, its pixel-art
source assets, and a throwaway host-side harness used to exercise the firmware
without the full laptop application. The device reads and debounces buttons,
validates USB messages, draws laptop-provided views and plays requested cues.
Timer, emotion and reward decisions stay on the laptop.

This replaces the earlier Raspberry Pi Pico + MicroPython plan. The `../pico/`
directory is retained but superseded; see [its README](../pico/README.md).

```text
tinyscreen/
├── firmware/            C++/Arduino sketch flashed to the board
├── sprites/             PNG source art, converted to firmware arrays
└── demo_game_loop.py    throwaway host harness (NOT the laptop application)
```

## 1. Board and capabilities

| Area | Verified value |
| --- | --- |
| Board | TinyCircuits **TinyScreen+** |
| MCU | Atmel/Microchip **ATSAMD21G18A**, ARM Cortex-M0+ (reported by `bossac` as chip ID `0x10010005`) |
| Memory/storage | 256KB flash (248KB usable above the 8KB bootloader), 32KB RAM |
| Bootloader | `v1.1 [Arduino:XYZ] Aug 15 2017`, BOSSA-compatible; `arduino-cli upload` drives it over USB |
| USB | Native USB CDC. Enumerates as "USB Serial Device", VID `0x03EB`, PID `0x8009`. Windows `BusReportedDeviceDesc` reads `TinyScreen+`. No REPL shares the stream, unlike MicroPython. |
| Power | Bus-powered over the USB data cable |
| Display | Built-in 96x64 color OLED, SSD1331 controller, on-board SPI — **no external display wiring** |
| Display driver | TinyCircuits `TinyScreen` Arduino library 1.1.0 |
| Buttons | **Four** built-in buttons, one at each screen corner |
| Time | `millis()`/`micros()`; wraparound handled by unsigned subtraction |
| Protocol data | ArduinoJson 7.4.3 parses/validates the 2,048-byte line limit |
| Scheduling | One cooperative `loop()`; no threads, RTOS or interrupts required so far |
| Expansion | Stacked MicroSD/Audio TinyShield (see section 4) |
| Networking | None on board; future HTTP services stay laptop-side |

### The `SerialUSB` gotcha

On this board's Arduino core, **`Serial` is the hardware UART on pins 0/1** — not
the USB connection. The USB CDC port the laptop opens is **`SerialUSB`**
(`variant.h` defines both `SERIAL_PORT_USBVIRTUAL` and `SERIAL_PORT_MONITOR` as
`SerialUSB`). Firmware that writes to `Serial` compiles and runs but is silently
invisible to the host, and never sees incoming bytes. All protocol I/O must use
`SerialUSB`.

### Buttons

All four are internal to the board; nothing is wired externally. The
`TinyScreen` library reads them with `digitalRead` on the TinyScreen+ path (its
I2C GPIO-expander path applies only to the older shield-style TinyScreen).

| Logical ID | Corner | Library constant | Core pin | Polarity | Verified |
| --- | --- | --- | --- | --- | --- |
| 1 | Top-left | `TSButtonUpperLeft` | 19 | Active-low, internal pull-up | Yes |
| 2 | Top-right | `TSButtonUpperRight` | 25 | Active-low, internal pull-up | Yes |
| 3 | Bottom-left | `TSButtonLowerLeft` | 30 | Active-low, internal pull-up | Yes |
| 4 | Bottom-right | `TSButtonLowerRight` | 31 | Active-low, internal pull-up | Yes |

Debounce (20 ms) and hold (600 ms) thresholds live in `firmware/hardware_config.h`
and match the values in [the serial protocol](../docs/serial_protocol.md).

### Display pins and orientation

The display's control pins are fixed on the board and owned by the library
(`DC` 22, `CS` 38, `SHDN` 27, `RST` 26); firmware never touches them directly.

`setFlip(true)` is applied at startup because the board is mounted rotated 180°
in its enclosure. `setFlip` rotates the drawn image **and** `getButtons()`'s
corner mapping together, so logical button IDs keep matching their physical
corners. Brightness is set to 11 of a valid 0–15.

### Color format

The library's 8-bit mode is **BGR332**: bits `[7:5]` blue, `[4:2]` green,
`[1:0]` red. Red therefore has only two bits, so arbitrary RGB values quantize
poorly; prefer the library's `TS_8b_*` constants for flat art. The one custom
color in use is `kInkColor` in `firmware/colors.h`.

## 2. Toolchain

MicroPython is **not** used. The firmware is C++ built with the Arduino toolchain.

| Item | Value |
| --- | --- |
| Builder | `arduino-cli` 1.5.1 |
| Board package | `TinyCircuits:samd` 1.1.0, from `https://files.tinycircuits.com/ArduinoBoards/package_tinycircuits_index.json` |
| FQBN | `TinyCircuits:samd:tinyscreen` |
| Libraries | `TinyScreen` 1.1.0, `ArduinoJson` 7.4.3 |

```sh
arduino-cli compile --fqbn TinyCircuits:samd:tinyscreen tinyscreen/firmware
arduino-cli upload -p <PORT> --fqbn TinyCircuits:samd:tinyscreen tinyscreen/firmware
```

The port must be free before uploading: `arduino-cli` resets the board over the
same CDC port, so stop any host process holding it first.

Current build size: ~187KB of 262KB (71%), dominated by the embedded audio clip.

## 3. Firmware layout

| File | Responsibility |
| --- | --- |
| `firmware.ino` | Cooperative loop: USB protocol, buttons, rendering, sound |
| `protocol.h/.cpp` | Wire protocol v2 framing, validation, connection/revision/epoch state |
| `buttons.h/.cpp` | Per-button debounce and press/hold gestures |
| `display.h/.cpp` | View state, screen layouts and bounded animation playback |
| `hardware_config.h` | Button table, timings and screen dimensions |
| `sprites.h`, `icons.h`, `colors.h` | Generated pixel data and shared colors |
| `sound.h/.cpp`, `sound_cues.h` | Non-blocking procedural tone cues |
| `audio_player.h/.cpp`, `audio_clip.h` | Looped PCM playback of an embedded clip |

Firmware may scan/debounce buttons, parse bounded messages, draw screens and play
cues. It must not decide timer outcomes, emotions, rewards or persistence.

### Asset pipeline

Source art is individual PNGs in `sprites/`, converted to BGR332 C arrays
(`sprites.h`, `icons.h`) by a one-off conversion script before flashing. The
firmware does not decode PNG at runtime and never receives frames over USB.
Transparent source pixels are baked to the background color they will sit on,
since the display has no alpha blending.

Naming convention: files sharing a `<name>` prefix with a trailing number
(`idle1.png`, `idle2.png`) are ordered frames of one `<name>` animation; a bare
`<name>.png` is a single static sprite.

## 4. MicroSD/Audio TinyShield

A TinyCircuits MicroSD/Audio TinyShield (ASD2205) is stacked on the board.

| Function | Connection | Status |
| --- | --- | --- |
| Audio out | DAC on pin `A0` into the shield's filter/amp | Working — procedural tones and embedded PCM both play |
| microSD | SPI, chip-select on pin 10 | **No card inserted**; `SD.begin(10)` returns false |

Audio today is generated in firmware: short square-wave cues for connect, button
press, feed and celebrate, plus an optional looped PCM clip embedded in flash.
Because the whole clip must fit in flash alongside the program, it is
downsampled to 8-bit/8kHz mono and truncated. Streaming a full-length file needs
a microSD card and an SD-reading playback path, neither of which exists yet.

## 5. Verified end-to-end

Confirmed on the physical device this bring-up:

- Display draws sprites, icons and text; orientation and brightness correct.
- All four buttons report clean, correctly-identified press gestures.
- USB CDC protocol round-trips: `hello` → `ready`, `ping` → `pong`, and physical
  presses arrive as `button` messages with the right IDs.
- Screen switching driven entirely by laptop-sent views.
- Audio plays through the shield's speaker.

Still unverified: hold gestures on the physical buttons, heartbeat-timeout
behavior, animation cue playback, and the performance measurements below.

## Performance record

Complete during real-device acceptance (M21). Measure before considering a
custom plaintext or binary protocol.

| Scenario | Line bytes | Decode + validation | Display update | Free-memory change | Button → render |
| --- | --- | --- | --- | --- | --- |
| Timer render | TBD | TBD | TBD | TBD | TBD |
| Largest valid fixture | TBD | TBD | TBD | TBD | TBD |

## The host harness

`demo_game_loop.py` is a throwaway Python harness that plays the laptop's role
well enough to exercise firmware screens without running the real application.
It is **not** the laptop app in [`../laptop/`](../laptop/) and owns no game
rules, persistence or event log. Use it for firmware bring-up only; use
`laptop/main.py --profile hardware` for real behavior.
