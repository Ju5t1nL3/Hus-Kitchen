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
```

Use `uv run ruff format .` to format laptop code. Commit `uv.lock`; do not commit
`.venv/`. Python 3.14 is independent of the MicroPython release in `../pico/`.
The Pico reuses this locked Ruff executable with its own provisional
`../pico/ruff.toml`; follow the [Pico bring-up sequence](../pico/README.md) before
treating that syntax target as verified.

There is no runnable application entry point yet. Add real run/report commands as
their tasks are completed instead of documenting placeholders as working software.

## Planned layout

```text
laptop/
├── pyproject.toml
├── uv.lock
├── .python-version
├── config.yaml                 # added with configuration task M11
├── src/deskpet/
│   ├── core/
│   ├── features/
│   ├── app/
│   └── adapters/
└── tests/
```

See [`../docs/system_design.md`](../docs/system_design.md) for module boundaries
and [`../docs/todo.md`](../docs/todo.md) before implementing a task.
