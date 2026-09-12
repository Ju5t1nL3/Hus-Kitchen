# Implementation guidelines

Use this when writing or reviewing code. The goal is easy-to-change hackathon
code. Tooling is initialized, while application and firmware behavior remain to
be implemented.
For the plain-language project explanation, read [the overview](overview.md).

Laptop tooling is initialized under `laptop/`: CPython 3.14.6, uv, Ruff and Pyright.
Run its commands from that directory. Firmware records its independent MicroPython
release in `pico/MICROPYTHON_VERSION` after the existing board setup is identified.

## Keep each rule in one place

Put food handling in feeding, focus/break transitions in timers, and expression
selection in emotions. Pass resources into classes so tests can substitute a fake
clock or device.
Use small functions for calculations and classes for resources that need to stay
open, such as the USB connection.

DRY means keeping one authoritative definition of a rule or fact. Reaction durations
belong in configuration; protocol limits belong with the protocol. Avoid a giant
global constants file. Do not create an abstraction just because two short pieces
of code happen to look similar. Laptop and firmware may have separate protocol
implementations, checked against the same examples.

Keep button bindings and action definitions separate from game rules. Use the
same definitions to resolve input and draw labels; adding a button uses declared
IDs/pins instead of new per-button branches. Follow the [class design](class_design.md)
recipe rather than creating a generic plugin framework.

## Make inputs and outputs explicit

- Annotate laptop function parameters and return values. Use named records for
  related fields instead of passing unstructured dictionaries between modules.
- Use enums or literal types for fixed choices such as mode, gesture and rejection
  code. Use a typed union of distinct records for commands and event payloads, so
  a completion event cannot accidentally carry a feeding payload.
- Before parallel implementation, implement the concrete records/unions for
  `RuntimeState`, `ControlIntent`, `ScheduleResult`, `PresentationResult` and
  `ParseResult` from the [class design](class_design.md). Keep definitions there and
  in their eventual owning code, rather than copying them into this guide.
- Prefer immutable records and collections for shared game data. Ordinary user
  mistakes return a rejection; storage failures and corrupt history raise explicit
  errors. Follow the existing API contracts.
- Whoever claims the laptop-bootstrap task selects one static type checker and
  commits its settings with the initial scaffold. Require strict checking of first-party laptop
  code before merging. Isolate untyped library calls in adapters; keep necessary
  exceptions narrow and explained. Do not bypass errors with widespread `Any`.

Type annotations do not validate incoming data. Validate YAML configuration, stored
events, and USB messages when reading them, then pass validated records inward.
Feature functions still enforce business rules, such as resuming only a paused
session and excluding paused time from the early-end grace calculation.
MicroPython may use validated dictionaries and small classes; it does not need
laptop dataclasses or the laptop's type-checker configuration.

## Keep host and hardware details at the edges

- Do not hardcode `COM3`, `/dev/tty*` or any detected port. Accept an optional
  configured port and otherwise resolve one unique device from enumerated metadata.
- Treat zero or multiple matching devices as explicit, actionable results. Do not
  select the first device based on enumeration order.
- Keep OS-specific serial behavior inside the serial adapter. Core, features and
  app orchestration must behave identically on Windows, macOS and Linux.
- Keep GPIO numbers and display-controller calls inside Pico configuration/drivers.
  Laptop behavior depends only on protocol capabilities, not board identity.
- Test discovery with fake Windows and POSIX port names. Hardware smoke tests remain
  necessary because mocks cannot prove USB driver or MicroPython behavior.

## Use Twelve-Factor selectively

[Twelve-Factor](https://12factor.net/) was written for software delivered as a
service. The choices below are our adaptations for a local USB companion, not a
claim of full compliance.

| Principle | How we apply it |
| --- | --- |
| Codebase and dependencies | Keep code in git; declare laptop dependencies and lock versions. Document firmware/driver versions separately. |
| Configuration | Keep tunable rules in YAML. Supply future secrets outside git, such as through environment variables. YAML is an intentional departure from environment-only configuration. |
| Attached resources | Access SQLite, USB and future integrations through replaceable interfaces. Keep SQLite local. |
| Build, release and run | Document installation, firmware flashing and application startup separately. Running the app should not silently install dependencies. |
| Processes and concurrency | Keep one authoritative game writer per database/device. Do not add stateless replicas or horizontal scaling to MVP. |
| Port binding | No HTTP service in MVP. Revisit only when an integration needs a listener. |
| Startup and shutdown | Restore saved state, close resources cleanly and handle crashes using the defined recovery policy. |
| Development/demo parity | Use the same rules and message formats with fake and real devices; validate on hardware before the demo. |
| Logs | Send laptop diagnostics to stderr; never mix firmware debug output into USB messages. The durable gameplay event database has a separate purpose. |
| Admin tasks | Run recap and future maintenance commands separately, reusing existing storage/query code. |

## What to check before merging

Check types, run relevant behavioral tests, and verify affected caller/callee and
message contracts still agree. Update the owning specification when an interface
changes. The [hackathon plan](hackathon_plan.md) owns the detailed acceptance checks.
Do not add services, frameworks or extra layers solely to satisfy a methodology.
