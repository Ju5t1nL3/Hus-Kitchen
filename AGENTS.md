# Tamagotchi Desk Pet — start here

A physical productivity companion: a laptop owns the game; a USB-connected
TinyCircuits TinyScreen+ displays the pet and reports buttons. The goal is to
replace phone-checking with a pleasant, glanceable desk device.

Current scope: large home pet and clock, a 5–60-minute focus selector, countdown,
four context-labeled buttons, focus pause/resume and calculated break offers. The
approved expansion now includes XP, levels, spendable `yarn`, priced Food/Drink,
the mood catalog, base/focus-chain rewards, and opt-in keyboard-count and
camera-attention yarn. Press Home button 3 (a gear icon) for Settings; keyboard and camera both
default Off. Level-up/daily-streak bonuses and weekly recap follow.
Health/hunger/friendship remain removed. Timer progress art is a separate future
idea, not the XP bar.

For a short, plain-language introduction, read [the overview](docs/overview.md).
Use the detailed specifications as task-specific references, not a required
cover-to-cover reading sequence.

## Required task tracking

Before starting work, open [docs/todo.md](docs/todo.md), claim the relevant MVP row
with your GitHub username (or the documented initials/agent fallback), and mark it
`[ ] Doing`. Respect existing claims and coordinate overlapping files. Update
progress/blockers while working and before handing off; mark `[x] Done` only after
its completion check passes, with a short result/reference. Add a row for authorized
MVP work if needed. Do not claim or check off future roadmap features as MVP work.

There are four team members, possibly only two on software. Tasks are self-selected;
do not preassign people to modules or assume a permanent integration owner.

## Project status

This repository contains implemented laptop rules, persistence, presentation,
USB adapters, application coordination/recovery and a development simulator,
alongside working TinyScreen+ firmware.
Use [docs/todo.md](docs/todo.md) for exact verified status; do not describe planned
modules or checks as working code.

The device is a TinyCircuits **TinyScreen+** (ATSAMD21G18A) with a built-in 96x64
OLED and four corner buttons, programmed in **C++/Arduino** with `arduino-cli`.
It replaced the earlier Raspberry Pi Pico + external-LCD prototype, whose display
never worked reliably. Firmware lives in [`tinyscreen/`](tinyscreen/); the
superseded MicroPython prototype is retained in [`pico/`](pico/) but is not
flashed or executed. The verified hardware record is in
[tinyscreen/README.md](tinyscreen/README.md).

The laptop runtime is CPython 3.14.6. An HP Windows laptop builds, flashes and
talks to the device over USB; keep application code device- and OS-agnostic
rather than hardcoding a Windows serial port.

The user explicitly asked to improve this file and the previous architecture,
not preserve their original structure. Their priorities are modularity,
maintainability, easy updates, and independent hackathon work with minimal merge
conflicts. See [design_decisions.md](docs/design_decisions.md) for rationale and assumptions.

Preserve portability: never hardcode `COM` names, `/dev` paths, OS checks or a
specific board/display inside core, feature or application modules. Put host
serial discovery in a laptop adapter (its USB identity belongs in configuration)
and pins/drivers in firmware hardware configuration. The board swap proved this
rule's worth: it needed no change to game rules or the wire protocol.

## Documentation map

Supporting documents live in `docs/`; keep this entry point at the repository root.

| Document | Owns | Read when |
| --- | --- | --- |
| [overview.md](docs/overview.md) | Plain-language introduction and example workflow | Understanding the project before implementation details |
| [todo.md](docs/todo.md) | MVP task claims, status, completion checks and handoffs | Required before starting work and when updating/finishing it |
| [features_and_goals.md](docs/features_and_goals.md) | Product goals, MVP behavior, acceptance criteria | Starting any feature |
| [components.md](docs/components.md) | Hardware inventory, unknowns, hardware boundary | Wiring, drivers, device setup |
| [system_design.md](docs/system_design.md) | Runtime architecture, dependencies, lifecycle, planned folders | Understanding how pieces connect |
| [class_design.md](docs/class_design.md) | Types, class/function inputs and outputs, error contracts | Implementing or calling an interface |
| [implementation_guidelines.md](docs/implementation_guidelines.md) | Typing, validation, DRY and project-specific Twelve-Factor choices | Writing or reviewing code |
| [serial_protocol.md](docs/serial_protocol.md) | Exact laptop ↔ device wire format and examples | Firmware, serial adapter, simulator |
| [development_modes.md](docs/development_modes.md) | Dev/hardware profiles, clickable virtual device and wire trace | Building or using the simulator/composition root |
| [event_model.md](docs/event_model.md) | Durable events, pause timing, emotion selection, replay and streaks | Game rules, persistence, reports |
| [hackathon_plan.md](docs/hackathon_plan.md) | Task-based coordination, integration order and verification | Picking up or integrating work |
| [nice_to_haves.md](docs/nice_to_haves.md) | Ordered future ideas and extension points | Considering future scope |
| [progression_design.md](docs/progression_design.md) | Active expansion: XP, levels, yarn, priced feeding, rewards and optional activity inputs | Reviewing or implementing progression |
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
- Keep laptop tooling under `laptop/`: run uv, Ruff and Pyright there. Firmware is
  a separate C++/Arduino toolchain (`arduino-cli`, pinned board package and
  libraries) under `tinyscreen/`; neither side imports from the other.
- Keep business rules on the laptop. Firmware may debounce, validate messages,
  animate, and detect a lost connection, but cannot calculate breaks, advance or
  pause sessions, choose emotions, interpret button actions, or persist game state.
- Separate durable GameState, temporary RuntimeState, and render data.
  Render data is a projection, never the source of truth.
- Use the reducer-style flow documented in system design: decide, save the event,
  apply_event, then present. Live updates and replay share the same pure transition
  function; resource I/O stays in the coordinator/adapters.
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
- Keep `dev` and `hardware` as composition profiles over the same rules and codec.
  Simulator clicks must traverse encoded/decoded JSON rather than call game rules
  directly; diagnostic traces are not durable gameplay events.

## Product principles

- No death, irreversible loss, or punishment for pausing or taking a break.
  Early-ended focus can cause brief sadness. Feed opens a priced purchase menu;
  insufficient yarn leaves state unchanged.
- Local-first: MVP data stays on the laptop. Future network or sensor features
  must have a clear purpose and explicit opt-in.
- Keyboard and camera tracking must have independent on/off controls. They add
  completion yarn; disabling them cannot remove base XP/yarn rewards. Never store
  key identities, typed text, camera frames, video, identity or face recognition.
- Home emphasizes a large pet and clock. Break emphasizes a legible central
  timer and small face. Focus emphasizes a legible timer to the right of an
  animated working-cat sprite on the left. Every bound physical button shows a visible label
  for its current action, drawn in that button's own screen corner; unbound
  buttons show a disabled dash. No stat bars or timer progress art in MVP.
- C++/Arduino is the firmware runtime. Verify actual hardware before choosing
  pins, drivers, or connector assumptions.
