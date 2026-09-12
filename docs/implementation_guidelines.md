# Implementation guidelines

Use this when writing or reviewing code. The goal is easy-to-change hackathon
code. These are implementation expectations; tooling and code do not exist yet.
For the plain-language project explanation, read [the overview](overview.md).

## Keep each rule in one place

Put feeding rules in the pet feature, timer rules in focus, and purchase rules in
shop. Pass resources into classes so tests can substitute a fake clock or device.
Use small functions for calculations and classes for resources that need to stay
open, such as the USB connection.

DRY means keeping one authoritative definition of a rule or fact. Food prices
belong in configuration; protocol limits belong with the protocol. Avoid a giant
global constants file. Do not create an abstraction just because two short pieces
of code happen to look similar. Laptop and firmware may have separate protocol
implementations, checked against the same examples.

## Make inputs and outputs explicit

- Annotate laptop function parameters and return values. Use named records for
  related fields instead of passing unstructured dictionaries between modules.
- Use enums or literal types for fixed choices such as mode, gesture and rejection
  code. Use a typed union of distinct records for commands and event payloads, so
  a completion event cannot accidentally carry a feeding payload.
- Before parallel implementation, finish the concrete types for `UiState`,
  `CommandIntent`, `ScheduleResult`, `PresentationResult` and `ParseResult` in the
  [class design](class_design.md). Keep exact definitions there and in their
  eventual owning code, rather than copying them into this guide.
- Prefer immutable records and collections for shared game data. Ordinary user
  mistakes return a rejection; storage failures and corrupt history raise explicit
  errors. Follow the existing API contracts.
- The integration owner selects one static type checker and commits its settings
  with the initial laptop scaffold. Require strict checking of first-party laptop
  code before merging. Isolate untyped library calls in adapters; keep necessary
  exceptions narrow and explained. Do not bypass errors with widespread `Any`.

Type annotations do not validate incoming data. Validate YAML configuration, stored
events, and USB messages when reading them, then pass validated records inward.
Feature functions still enforce business rules, such as sufficient coins.
MicroPython may use validated dictionaries and small classes; it does not need
laptop dataclasses or the laptop's type-checker configuration.

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
