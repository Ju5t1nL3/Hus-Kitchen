# MVP task board

This is the source of truth for task ownership and progress. There are four team
members, but possibly only two working on software. Anyone can claim an available
task; there are no assigned people, permanent roles or department ownership.

Only MVP work belongs here for now. Add further milestones when the team chooses
to start them; the future roadmap is not an active implementation checklist.

## How to use this board

1. Before working, read the relevant spec and claim a row: replace Owner's dash
   with your GitHub username and set Status to `[ ] Doing`. Initials are fine if
   you have no username recorded. An LLM uses the invoking person's known handle
   plus `(AI)`; if unknown, use `agent:<task-label>` rather than inventing a name.
2. Check existing claims before editing overlapping files. Do not take another
   person's task without a handoff. Share the claim through the team's normal
   collaboration workflow; an unsynced local edit cannot reserve a task for everyone.
3. Keep the row current. If blocked, use `[ ] Blocked` and name the missing input
   or dependency in Notes. If handing off, record what is done and what remains;
   clear Owner and return to `[ ] Todo` when the task is available again.
4. Mark `[x] Done` only after the completion check passes. Keep the owner's name
   and add a short check/result or PR/commit reference. A plan or unverified code
   is not completion. Update the row before ending your work session.
5. Change only the rows you need; preserve IDs and other people's notes. Add a
   new MVP row if authorized work does not fit an existing task. Split large tasks
   when useful instead of silently taking ownership of a whole folder.

Status values: `[ ] Todo`, `[ ] Doing`, `[ ] Blocked`, `[x] Done`.
“Needs” lists inputs needed to finish/integrate a task; independent work can start
against agreed interfaces and fakes. Check the linked specs before implementing.

## Setup and shared contracts

References: [decisions](design_decisions.md), [hardware](components.md),
[class design](class_design.md), [implementation guidance](implementation_guidelines.md).

| Owner | Status | ID | Task / completion check | Needs | Notes |
| --- | --- | --- | --- | --- | --- |
| agent:task-board | [x] Done | M00 | Publish this MVP board and contributor claim/update rules; links and workflow agree. | — | Verified 77 local links, table formatting and 23 task IDs; removed preset assignments and updated setup/open-choice notes. |
| agent:laptop-bootstrap | [ ] Blocked | M02 | Record laptop OS and Python version, then confirm serial access and the supported environment. | User's choice | CPython 3.14.6 and macOS 26.5.2 recorded. Blocked only on confirming USB serial access with the actual device and deciding whether other OSes are supported. |
| agent:laptop-bootstrap | [x] Done | M03 | Create laptop package/dependency setup and static-checker configuration; basic import/check command works. | M02 | Laptop-local uv project created. `uv sync`, package import, Ruff format/check, and strict Pyright passed; uv.lock pins Ruff 0.16.7 and Pyright 1.1.414. |
| — | [ ] Todo | M04 | Implement typed records, commands, event payloads and resource interfaces; type checks pass. | M03 | Follow existing API/event/wire specs; no future reward or sensor types. |
| — | [ ] Todo | M05 | Add shared protocol/event examples and fake clock, device and store; both sides have agreed test inputs. | M04 | Include pause/end boundary and extra-button examples. |

## Laptop behavior and persistence

References: [MVP behavior](features_and_goals.md), [events](event_model.md),
[architecture](system_design.md), [class design](class_design.md).

| Owner | Status | ID | Task / completion check | Needs | Notes |
| --- | --- | --- | --- | --- | --- |
| — | [ ] Todo | M06 | Implement focus/break rules: duration selection, break calculation, pause/resume, completion and active-time grace boundary. | M04, M05 | Cover 59.999s vs 60s, paused End and neutral break ending. |
| — | [ ] Todo | M07 | Implement one-food feeding and event-driven emotions; newest reaction expires correctly without hidden stats. | M04, M05 | Reaction durations stay configurable/provisional. |
| — | [ ] Todo | M08 | Implement deterministic event replay and state transitions; golden history rebuilds exactly; invalid history fails clearly. | M04, M05 | No clock/config reads or animation side effects during replay. |
| — | [ ] Todo | M09 | Implement SQLite append/read, uniqueness, writer lock and storage errors; commits survive reopen and retries cannot duplicate outcomes. | M04, M05 | Test terminal and break-choice conflicts. |
| — | [ ] Todo | M10 | Implement streak and weekly text recap; pauses/breaks excluded and cumulative samples not double counted. | M08, M09 | Dashboard and reward accounting are outside MVP. |
| — | [ ] Todo | M11 | Implement validated configuration, action definitions and button bindings; remapping changes behavior and labels together. | M04, M05 | Simulate a third button without editing timer rules. |
| — | [ ] Todo | M12 | Implement screen presenter for Home/setup/focus/paused/break offer/break; snapshots match the wire contract. | M06, M07, M11 | Large timer, small face, correct labels and control epochs. |
| — | [ ] Todo | M13 | Implement laptop wire codec; fragmented, combined, invalid and oversized messages behave as specified. | M04, M05 | Validate declared button IDs and full views. |
| — | [ ] Todo | M14 | Implement threaded USB link, bounded queues, heartbeat and reconnect; latest view restores and stale input is discarded. | M13 | Use a fake endpoint while hardware is unavailable. |

## Pico and artwork

References: [components](components.md) and [serial protocol](serial_protocol.md).
Inspect the actual setup before replacing or repeating work already done.

| Owner | Status | ID | Task / completion check | Needs | Notes |
| --- | --- | --- | --- | --- | --- |
| — | [ ] Todo | M01 | Complete `pico/README.md` in order: (1) inventory all project-relevant board capabilities and existing work, including GPIO/buttons, display/bus/driver, USB, memory, timing, JSON, files, reset, scheduling and expansion needs; (2) select, flash and smoke-test a stable MicroPython build for the exact board, then pin its release, UF2 URL and checksum in `MICROPYTHON_VERSION` and the README; (3) align `pico/ruff.toml` to a conservative supported syntax target, run Ruff and verify on-device. | Existing hardware | The README contains the reporting template. Reuse the breadboard; do not rebuild working hardware. Ruff's target alone does not prove MicroPython compatibility. |
| — | [ ] Todo | M15 | Complete/verify hardware configuration and generic button scanning; clean press-or-hold events carry declared IDs/epochs. | M01, M05 | Reuse existing wiring/code where present; verify debounce and held-button reset. |
| — | [ ] Todo | M16 | Create/verify LCD layouts and sprites: full pet, six small-face moods, food, feeding and celebration; drawing remains responsive. | M01, M05 | Match confirmed display dimensions; reuse existing assets/driver. |
| — | [ ] Todo | M17 | Integrate firmware codec/main loop, buttons and rendering; handshake, disconnect overlay and recorded views work on Pico. | M15, M16 | No laptop game logic on firmware; no debug output in protocol stream. |

## Integration and MVP verification

References: [integration plan](hackathon_plan.md) and [acceptance checks](features_and_goals.md).

| Owner | Status | ID | Task / completion check | Needs | Notes |
| --- | --- | --- | --- | --- | --- |
| — | [ ] Todo | M18 | Wire laptop coordinator/scheduler and entry point: button → decision → saved event → view; due completion precedes controls. | M06–M09, M11–M14 | Build a minimal vertical slice early using fakes, then fill out the flow. |
| — | [ ] Todo | M19 | Verify restart, system-sleep, storage-failure and shutdown handling; unfinished timers end neutrally and pending breaks survive. | M18 | Saved elapsed lower bounds and no replayed animations. |
| — | [ ] Todo | M20 | Run full fake-device MVP scenarios and type checks; fix failures and record results. | M10, M18, M19 | Includes pause exclusion, stale control epoch and duplicate completion. |
| — | [ ] Todo | M21 | Run real-device acceptance checks; verify readable screens, feeding, timers, reconnect and measured response/refresh timing. | M17–M19 | Hardware evidence required; tuning values may remain open. |
| — | [ ] Todo | M22 | Document actual setup/run/flash/report commands and demo steps; reconcile docs with implemented interfaces. | M10, M20, M21 | No invented commands or blanket completion of unverified tasks. |

Existing hardware progress does not make an entire firmware task complete. Record
verified substeps in Notes and check the row only when its full completion check
passes. Open tuning and post-MVP reward/layout choices remain in
[design_decisions.md](design_decisions.md), not additional tasks on this MVP board.
