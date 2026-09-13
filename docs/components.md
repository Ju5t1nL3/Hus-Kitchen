# Components and hardware boundary

Status: the device is a TinyCircuits **TinyScreen+**, inspected and brought up
on-device. This replaces the earlier Raspberry Pi Pico + external-LCD plan, which
was never brought to a working display. The full verified inventory, pin table
and toolchain live in the [TinyScreen+ README](../tinyscreen/README.md); this
document records the stable facts and the hardware boundary.

| Component | MVP role | Status |
| --- | --- | --- |
| Laptop | CPython 3.14.6 rules/timers, local SQLite history, serial connection | HP Windows laptop builds, flashes and talks to the device over USB |
| TinyCircuits TinyScreen+ | C++/Arduino display and button peripheral over USB | Confirmed: ATSAMD21G18A (Cortex-M0+), 256KB flash, 32KB RAM, native USB CDC (VID `0x03EB`, PID `0x8009`) |
| Built-in 96x64 OLED | Home pet/clock, setup, large countdown and button labels | Confirmed: SSD1331 controller, 8-bit color, on-board SPI, driven by the TinyScreen library. No external wiring |
| Four built-in buttons | One per screen corner, press or hold | Confirmed: IDs 1–4 map top-left, top-right, bottom-left, bottom-right; active-low with internal pull-ups |
| USB data cable | Power and data | Confirmed: programs the board and carries the application protocol |
| MicroSD/Audio TinyShield (ASD2205) | Audio out; future file storage | Audio DAC on `A0` confirmed working. microSD present but **no card inserted** |

The original "Pico / Pi Zero W" ambiguity and the 128x160 ST7735S LCD plan are
both superseded. The Pico's display never reached a reliable state (see the
[Pico README](../pico/README.md) for that trail); the TinyScreen+ removes the
problem entirely by integrating display and buttons on one board.

The expected deployment host is an HP Windows laptop. Keep laptop code
OS-agnostic: discover/configure the serial port rather than hardcoding a Windows
`COM` name, and isolate OS-specific behavior behind adapters if it becomes
necessary. The device's USB identity belongs in laptop configuration, not in game
rules.

## Display and assets

The canvas is 96x64 — considerably smaller than the previously planned 128x160
panel, so layouts must stay sparse.

Because the four buttons sit at the screen's corners rather than in a row beneath
it, labels are drawn in the matching corners rather than as a bottom strip. Home:
large central pet, clock, and corner labels. Break: large central countdown with
a small face, and corner labels. Focus: countdown on the right beside an
animated mood sprite on the left, and corner labels. The progression
(level/yarn) strip occupies the bottom-right corner on Feed, which is why
button 4 is deliberately left unbound there; on Home that corner instead binds
Pet.

Four buttons are the current hardware, not a hardcoded scanner limit. Define ID,
corner slot and polarity per button in `tinyscreen/firmware/hardware_config.h`.
Iterate that table for scanning, advertising capabilities and drawing label
positions. Adding or removing a button needs a real hardware check and a laptop
binding, not new feeding or timer logic.

Provide individual PNG frames for Idle (2), Happy (2), Sad (2), Hungry (2),
Working Neutral (2), Working Sad (2), Sleeping (2), Eating (3), and Party (1).
Jollof Rice and Coffee have item sprites and share the Eating animation. Share
animation frames where practical. A face must remain recognizable at its small
size.

Keep source frames as individual PNG files, including two-frame animations.
Files sharing a `<name>` prefix with a trailing frame number are ordered frames
of one `<name>` animation; a bare `<name>.png` is a single static sprite. Convert
those PNG sources into firmware bitmap arrays before deployment; the firmware
does not decode PNG files or receive frames over USB at runtime.

The display's 8-bit mode is BGR332 — blue and green get three bits each, red only
two — so arbitrary RGB values quantize poorly and flat art should prefer the
library's own color constants. There is no alpha channel: transparent source
pixels are baked to whatever background they will sit on.

Firmware draws the laptop-selected mood, text, food and button labels. It may
debounce, animate and format seconds, but cannot calculate breaks, pause the game,
choose an emotion, interpret an action or track a hidden pet stat.

## Sound

Audio is now real hardware rather than a future idea. The stacked shield's DAC on
pin `A0` drives a filter/amp and speaker. Firmware plays short procedural tone
cues (connect, button press, feed, celebrate) and can loop a PCM clip embedded in
flash. Full-length file playback would need a microSD card — the slot exists but
is empty — plus an SD-reading playback path that does not exist yet. Sound
remains outside the MVP acceptance checks.

## Bring-up

The ordered inventory, pin table, toolchain and verified/unverified status live
in the [TinyScreen+ README](../tinyscreen/README.md). Record stable hardware facts
here; keep the reproducible firmware record with the firmware.

One board-specific trap is worth repeating because it silently breaks all
communication: on this Arduino core, `Serial` is the hardware UART on pins 0/1,
while the USB CDC port the laptop opens is `SerialUSB`. Protocol I/O must use
`SerialUSB`.

Use a fake laptop device link and recorded screen examples during independent
development. The [serial protocol](serial_protocol.md) is the shared contract;
display hardware stays behind the firmware's rendering layer.
