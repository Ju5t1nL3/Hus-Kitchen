# Tamagotchi Desk Pet

Your portable key to productivity! 

Tomatchi is a digital pet, desk clock, and Pomodoro timer, all in one tiny screen. 
A USB-powered TinyCircuits TinyScreen+ reads button presses and
renders the screen. Plug it into your laptop to activate the corresponding laptop app, which manages all of the logic, timers,
emotions and history.

This repository contains two separate runtimes:

- [`laptop/`](laptop/) — CPython 3.14.6 application, managed with uv.
- [`tinyscreen/`](tinyscreen/) — C++/Arduino firmware, built and flashed with
  `arduino-cli`.

They communicate using the versioned JSON Lines protocol described in
[`docs/serial_protocol.md`](docs/serial_protocol.md). 

[`pico/`](pico/) holds a superseded Raspberry Pi Pico + MicroPython prototype that was abandoned,
retained for debugging record only. 

The expected demo host is an HP Windows laptop, but the application is designed
to remain OS- and device-agnostic. Serial ports are discovered or configured at
the adapter boundary. Platform paths and board/display details never enter game
rules. Initial laptop tooling has also been verified on macOS.

Start with [`AGENTS.md`](AGENTS.md) for contributor rules and the documentation map.
Read [`docs/overview.md`](docs/overview.md) for the short product explanation and
[`docs/todo.md`](docs/todo.md) before claiming implementation work.

The implemented [`dev` profile](docs/development_modes.md) provides a clickable
virtual device and bidirectional JSON trace. The `hardware` profile runs the same
application and rules against the real USB device and persistent database.

## Repository layout

```text
AGENTS.md              contributor and LLM entry point
README.md              repository overview
docs/                  product, architecture and task documents
contracts/             runtime-neutral protocol and event fixtures
laptop/                CPython application and laptop tooling
tinyscreen/            C++/Arduino firmware, sprite sources and hardware record
pico/                  superseded MicroPython prototype, retained for reference
```

The laptop foundation, simulator and progression/economy expansion are
implemented, and the TinyScreen+ firmware renders laptop-sent views and reports
its four buttons. Full end-to-end acceptance against the real device remains on
the task board. Use the per-runtime READMEs for verified commands rather than
assuming planned work already runs.
