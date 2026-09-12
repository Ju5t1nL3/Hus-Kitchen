# Tamagotchi Desk Pet

A small physical productivity companion. A laptop application owns timers,
emotions and history; a USB-connected Raspberry Pi Pico reads buttons and renders
the screen.

This repository contains two separate Python runtimes:

- [`laptop/`](laptop/) — CPython 3.14.6 application, managed with uv.
- [`pico/`](pico/) — MicroPython firmware, flashed separately to the exact board.

They communicate using the versioned JSON Lines protocol described in
[`docs/serial_protocol.md`](docs/serial_protocol.md). They share protocol contracts,
but never import code from each other.

The expected demo host is an HP Windows laptop, but the application is designed
to remain OS- and device-agnostic. Serial ports are discovered or configured at
the adapter boundary; platform paths and board/display details never enter game
rules. Initial laptop tooling has also been verified on macOS.

Start with [`AGENTS.md`](AGENTS.md) for contributor rules and the documentation map.
Read [`docs/overview.md`](docs/overview.md) for the short product explanation and
[`docs/todo.md`](docs/todo.md) before claiming implementation work.

The planned [`dev` profile](docs/development_modes.md) provides a clickable virtual
Pico and bidirectional JSON trace. The `hardware` profile runs the same application
and rules against the real USB device and persistent database.

## Repository layout

```text
AGENTS.md              contributor and LLM entry point
README.md              repository overview
docs/                  product, architecture and task documents
contracts/             runtime-neutral protocol and event fixtures
laptop/                CPython application and laptop tooling
pico/                  MicroPython firmware and hardware notes
```

The application is still at the scaffold/planning stage. Setup and run commands
will grow as the corresponding MVP tasks are implemented.
