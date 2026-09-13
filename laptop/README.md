# Laptop application

This folder contains the CPython application: timer and emotion rules, SQLite
history, screen presentation, USB communication and future laptop integrations.
It must not be copied to or imported by the Pico firmware.

The expected deployment host is an HP Windows laptop; initial tooling was also
verified on macOS. Keep serial discovery and application code OS-agnostic—never
hardcode a `COM` port or platform-specific device path in game logic.

## Tooling

- CPython 3.14.6, selected by `.python-version`; `pyproject.toml` accepts compatible
  3.14 patch releases when building the package elsewhere.
- uv manages the virtual environment, dependencies and `uv.lock`.
- Ruff formats and lints laptop code.
- Pyright performs static type checking.

From this folder:

```sh
uv sync
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run python -m unittest discover -s tests -v
```

Use `uv run ruff format .` to format laptop code. Commit `uv.lock`; do not commit
`.venv/`. Python 3.14 is independent of the MicroPython release in `../pico/`.
The Pico reuses this locked Ruff executable with its own provisional
`../pico/ruff.toml`; follow the [Pico bring-up sequence](../pico/README.md) before
treating that syntax target as verified.

Run the hardware application from this folder after connecting the configured Pico:

```sh
uv run python main.py --profile hardware
```

Use `--config PATH` or `--data PATH` to override the default `config.yaml` and
`data/pet.db`. The application reports no matching or ambiguous serial devices
instead of guessing.

Run the clickable virtual Pico without hardware:

```sh
uv run python main.py --profile dev
```

Open the printed loopback URL (normally `http://127.0.0.1:8765`). Development
storage is temporary unless `--data PATH` is supplied. Use `--simulator-port`
to choose another local port. The simulator exposes connect/reboot controls,
three clickable buttons, fake-time advancement, invalid-line injection and a
bounded copyable JSON trace. Both runtime profiles use the same application,
rules, presenter, wire codec and event-store contract.

The [development and hardware profiles](../docs/development_modes.md) use
one application and wire codec. Development supplies a clickable virtual Pico and
safe temporary storage; hardware supplies the USB adapter and local SQLite store.

## Planned layout

```text
laptop/
├── pyproject.toml
├── uv.lock
├── .python-version
├── config.yaml                 # validated user-tunable rules and bindings
├── src/deskpet/
│   ├── core/
│   ├── features/
│   ├── app/
│   └── adapters/
└── tests/
```

See [`../docs/system_design.md`](../docs/system_design.md) for module boundaries
and [`../docs/todo.md`](../docs/todo.md) before implementing a task.
