# Tamagotchi Desk Pet — start here

A physical productivity companion: a laptop owns the game; a USB-connected
Raspberry Pi Pico displays the pet and reports buttons. The goal is to replace
phone-checking with a pleasant, glanceable desk device.

Current MVP: large home pet and clock, one free food, a 5–60-minute focus selector,
large countdown with a small expressive face, End/Pause/Resume, and optional
calculated breaks. Emotions come from events. Health/hunger/friendship are removed
from the product entirely. The first post-MVP milestone is XP, coins and level-up
bonuses, followed by optional typing/head-tracking bonuses. Timer progress art is
future idea #8, separate from the XP bar.

For a short, plain-language introduction, read [the overview](docs/overview.md).
Use the detailed specifications as task-specific references, not a required
cover-to-cover reading sequence.

## Project status

This repository currently contains planning documents, not an implementation.
The architecture, APIs, protocol, and directory tree are the proposed MVP baseline.
Do not describe planned modules or checks as already implemented.

The user explicitly asked to improve this file and the previous architecture,
not preserve their original structure. Their priorities are modularity,
maintainability, easy updates, and independent hackathon work with minimal merge
conflicts. See [design_decisions.md](docs/design_decisions.md) for rationale and assumptions.

## Documentation map

Supporting documents live in `docs/`; keep this entry point at the repository root.

| Document | Owns | Read when |
| --- | --- | --- |
| [overview.md](docs/overview.md) | Plain-language introduction and example workflow | Understanding the project before implementation details |
| [features_and_goals.md](docs/features_and_goals.md) | Product goals, MVP behavior, acceptance criteria | Starting any feature |
| [components.md](docs/components.md) | Hardware inventory, unknowns, hardware boundary | Wiring, drivers, device setup |
| [system_design.md](docs/system_design.md) | Runtime architecture, dependencies, lifecycle, planned folders | Understanding how pieces connect |
| [class_design.md](docs/class_design.md) | Types, class/function inputs and outputs, error contracts | Implementing or calling an interface |
| [implementation_guidelines.md](docs/implementation_guidelines.md) | Typing, validation, DRY and project-specific Twelve-Factor choices | Writing or reviewing code |
| [serial_protocol.md](docs/serial_protocol.md) | Exact laptop ↔ Pico wire format and examples | Firmware, serial adapter, simulator |
| [event_model.md](docs/event_model.md) | Durable events, pause timing, emotion selection, replay and streaks | Game rules, persistence, reports |
| [hackathon_plan.md](docs/hackathon_plan.md) | File ownership, integration order, verification | Splitting work or integrating changes |
| [nice_to_haves.md](docs/nice_to_haves.md) | Ordered future ideas and extension points | Considering future scope |
| [progression_design.md](docs/progression_design.md) | Next milestone: XP, coins, levels and optional activity bonuses | Reviewing or implementing progression |
| [design_decisions.md](docs/design_decisions.md) | User preferences, resolved conflicts, assumptions, open questions | Reconsidering a decision |

Start with this file and the MVP goals; then read the documents relevant to the
task. The overview summarizes the design; the detailed documents are canonical
for their respective topics. When a decision changes, update its owning document
and affected contracts in the same change.
User instructions override the plan; document material deviations.

## Engineering guidance

- Follow [implementation guidelines](docs/implementation_guidelines.md): check
  laptop types, validate external data, and apply Twelve-Factor only where it fits
  this local device. Keep methodology details in that guide.
- Keep business rules on the laptop. Firmware may debounce, validate messages,
  animate, and detect a lost connection, but cannot calculate breaks, advance or
  pause sessions, choose emotions, interpret button actions, or persist game state.
- Separate durable GameState, temporary RuntimeState, and render data.
  Render data is a projection, never the source of truth.
- Use feature modules and explicit typed inputs/outputs. Prefer pure functions
  for rules and small classes for stateful resources. Avoid a giant pet class,
  global mutable state, inheritance hierarchies, and a plugin framework in MVP.
- Dependencies point inward: adapters depend on contracts; game rules never
  import serial, SQLite, GPIO, HTTP, or display libraries.
- Persist an event before publishing its resulting state or animation.
  Replaying events must reproduce durable state without reissuing side effects.
- One laptop application loop owns state mutation. Background serial input
  feeds a queue that wakes it immediately; buttons cannot wait for a slow tick.
- Count only active focus time for completion and the 60-second early-end grace
  period. Record pause/resume transitions; no time spent paused counts as focus.
- Put tunable rules in laptop configuration and pin assignments in firmware
  configuration. Keep protocol limits and schema versions in their contracts.
- Keep button bindings declarative and independent of game rules. One action
  definition supplies both its label and behavior; new physical buttons use the
  same scanner/message path. See [class design](docs/class_design.md).
- Treat interfaces and shared configuration as coordinated files. Follow
  [hackathon_plan.md](docs/hackathon_plan.md); folder boundaries reduce conflicts but
  cannot guarantee nobody edits the same file.
- Build a working vertical slice before optional integrations. Do not create
  placeholder frameworks or empty implementations for every future idea.

## Product principles

- No death, irreversible loss, or punishment for pausing or taking a break.
  Early-ended focus can cause brief sadness; feeding is always free on Home.
- Local-first: MVP data stays on the laptop. Future network or sensor features
  must have a clear purpose and explicit opt-in.
- Keyboard and head tracking must have independent on/off controls. They add
  completion bonuses; disabling them cannot remove the base XP/coin reward.
- Home emphasizes a large pet and top-right clock. Focus/break views emphasize a
  legible central timer and small face at top right. Both physical buttons have
  visible labels for their current action; no stat bars or progress art in MVP.
- MicroPython is the planned firmware runtime. Verify actual hardware before
  choosing pins, drivers, or connector assumptions.
