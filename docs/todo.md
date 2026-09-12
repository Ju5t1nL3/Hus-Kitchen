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
| agent:laptop-bootstrap | [x] Done | M02 | Record laptop OS and Python version, then confirm USB device access and the supported environment. | User's choice | CPython 3.14.6; HP Windows is the expected host and successfully programmed/controlled the Pico over USB. Tooling also works on macOS 26.5.2. Code remains OS-agnostic; clean protocol traffic is tested in M14/M17. |
| agent:laptop-bootstrap | [x] Done | M03 | Create laptop package/dependency setup and static-checker configuration; basic import/check command works. | M02 | Laptop-local uv project created. `uv sync`, package import, Ruff format/check, and strict Pyright passed; uv.lock pins Ruff 0.16.7 and Pyright 1.1.414. |
| justinle2006 | [x] Done | M04 | Implement typed records, commands, event payloads and resource interfaces; type checks pass. | M03 | Added immutable core models, typed command/event/input/result unions, UI records and resource protocols. Ruff, strict Pyright and 7 contract tests pass. |
| justinle2006 | [x] Done | M05 | Add shared protocol/event examples and fake clock, device and store; both sides have agreed test inputs. | M04 | Added runtime-neutral JSONL protocol/event fixtures, exact 59.999s/60.000s outcomes, a third-button case and typed in-memory resources. Ruff, strict Pyright and all 17 tests pass. |

## Laptop behavior and persistence

References: [MVP behavior](features_and_goals.md), [events](event_model.md),
[architecture](system_design.md), [class design](class_design.md).

| Owner | Status | ID | Task / completion check | Needs | Notes |
| --- | --- | --- | --- | --- | --- |
| justinle2006 | [x] Done | M06 | Implement focus/break rules: duration selection, break calculation, pause/resume, completion and active-time grace boundary. | M04, M05 | Added pure typed timer decisions and configurable validated policies. Ruff, strict Pyright and all 31 tests pass, including 59.999s/60s, paused End, deadline priority and neutral interruption/break endings. |
| justinle2006 | [x] Done | M07 | Implement one-food feeding and event-driven emotions; newest reaction expires correctly without hidden stats. | M04, M05 | Added pure feeding decisions and mood selection with configurable food reaction duration. Ruff, strict Pyright and all 42 tests pass. |
| justinle2006 | [x] Done | M08 | Implement pure replay.apply_event and rebuild using the same transition function; incremental and rebuilt state match; invalid history fails clearly. | M04, M05 | Added immutable event reduction/rebuild with identity, sequence, session, progress, terminal and break-offer validation. Ruff, strict Pyright and all 62 tests pass. |
| justinle2006 | [x] Done | M09 | Implement SQLite append/read, uniqueness, writer lock and storage errors; commits survive reopen and retries cannot duplicate outcomes. | M04, M05 | Added transactional typed SQLite storage, native cross-platform writer locking, read-only access, idempotent retries and explicit conflict/corruption errors. All 13 variants round-trip; Ruff, strict Pyright and all 83 tests pass. |
| — | [ ] Todo | M10 | Implement streak and weekly text recap; pauses/breaks excluded and cumulative samples not double counted. | M08, M09 | Dashboard and reward accounting are outside MVP. |
| justinle2006 | [x] Done | M11 | Implement validated configuration, action definitions and button bindings; remapping changes behavior and labels together. | M04, M05 | Added typed YAML config, canonical actions, validation, resolution, navigation and generic third-button support. Remapping drives behavior and labels together; Ruff, strict Pyright and all 75 tests pass. |
| liannie3 | [x] Done | M12 | Implement screen presenter for Home/setup/focus/paused/break offer/break; snapshots match the wire contract. | M06, M07, M11 | Implemented `app/presenter.py` (`build`/`on_commit`) and `features/emotions.py` (`select`, per event_model.md). `tests/app/test_presenter.py` reconstructs all 7 independent screen fixtures from serial_protocol.md and asserts exact RenderSnapshot field equality, plus on_commit navigation/cue cases (session start, focus completion, feed, break). `uv run ruff check`, `uv run ruff format` and `uv run pyright` all pass; `python -m unittest discover -s tests` is 42/42 green (installed `uv` locally via pip since it wasn't on PATH here; also added `tzdata` as a Windows dependency in pyproject.toml since `zoneinfo` has no tz database on Windows without it, which was failing even the pre-existing M06 timer tests). Added a minimal `app/controls.py::labels()` (press/hold/unbound resolution only, no validation/resolve/navigate) as a stand-in for M11's real bindings loader — presenter's tests build their own fixture bindings/actions, not real config, so this is not yet exercised against actual M11 output. `on_commit`'s PetFed branch is tested against a synthetic event, not yet wired to `features/feeding.py::decide` (now done by M07) end-to-end. |
| justinle2006 | [x] Done | M13 | Implement laptop wire codec; fragmented, combined, invalid and oversized messages behave as specified. | M04, M05 | Added incremental bounded framing, strict protocol-v2 validation, complete-view/declared-button checks and exact compact fixture encoding. Ruff, strict Pyright and all 96 tests pass. |
| justinle2006 | [x] Done | M14 | Implement portable serial discovery plus the threaded USB link, bounded queues, heartbeat and reconnect; latest view restores and stale input is discarded. | M13 | Added deterministic metadata/port resolution, pyserial adapter, reconnecting reader/pump workers, atomic writes, handshake and heartbeat validation, latest-view restoration, bounded/coalesced output, and stale-input rejection. Windows/POSIX fake coverage; 108 tests plus Ruff and strict Pyright pass. |

## Developer simulator

Reference: [development and hardware modes](development_modes.md).

| Owner | Status | ID | Task / completion check | Needs | Notes |
| --- | --- | --- | --- | --- | --- |
| — | [ ] Todo | M23 | Implement explicit `dev`/`hardware` composition profiles and a clickable virtual Pico with screen, dynamic buttons, fake-time controls and bounded bidirectional JSON trace; a full focus/break flow and invalid/reconnect cases traverse the production codec. | M11–M14, M18 | Same rules/presenter/codec in both profiles. Dev storage is temporary by default; browser UI binds loopback only. No direct button-to-feature calls or gameplay events for diagnostics. |

## Pico and artwork

References: [components](components.md) and [serial protocol](serial_protocol.md).
Inspect the actual setup before replacing or repeating work already done.

| Owner | Status | ID | Task / completion check | Needs | Notes |
| --- | --- | --- | --- | --- | --- |
| agent:pico-bringup (AI) | [ ] Doing | M01 | Complete `pico/README.md` in order: (1) inventory all project-relevant board capabilities and existing work, including GPIO/buttons, display/bus/driver, USB, memory, timing, JSON, files, reset, scheduling and expansion needs; (2) select, flash and smoke-test a stable MicroPython build for the exact board, then pin its release, UF2 URL and checksum in `MICROPYTHON_VERSION` and the README; (3) align `pico/ruff.toml` to a conservative supported syntax target, run Ruff and verify on-device. | Existing hardware | RP2040 confirmed; display is a 128x160 ST7735S SPI TFT. Board already enumerates as a MicroPython CDC device (VID 2E8A, PID 0005) on COM6, so firmware is already flashed. Buttons confirmed by scanning GPIO0-22/26-28 for a live press: button 1 (left) is GPIO10, button 2 (right) is GPIO11, both active-low with internal pull-up (docs previously said GPIO14/15, which never toggled on press and were wrong). Still needed: exact board variant beyond "RP2040 Pico non-W", display bus pins, driver source, memory/power/reset/scheduling inventory rows. |
| agent:pico-bringup (AI) | [ ] Doing | M15 | Complete/verify hardware configuration and generic button scanning; clean press-or-hold events carry declared IDs/epochs. | M01, M05 | `hardware_config.py`/`buttons.py` copied to the board via mpremote. Physical press/release confirmed on-device: with corrected pins (GPIO10/GPIO11, not the originally-recorded GPIO14/15), `ButtonScanner.poll()` reports a clean `press` gesture with the correct button id for each real tap of both buttons, visually confirmed via the GPIO2 test LED blinking on each detected gesture. Still open: a held-button (hold-gesture) test, and confirming debounce timing (20ms) tolerates the actual switches without chatter under repeated rapid presses. |
| — | [ ] Todo | M16 | Create/verify LCD layouts and sprites: full pet, six small-face moods, food, feeding and celebration; drawing remains responsive. | M01, M05 | Match confirmed display dimensions; reuse existing assets/driver. Blocked on display bus pin confirmation from M01. |
| agent:pico-bringup (AI) | [ ] Doing | M17 | Integrate firmware codec/main loop, buttons and rendering; handshake, disconnect overlay and recorded views work on Pico. | M15, M16 | `protocol.py`/`display.py`/`main.py` copied to the board via mpremote; `Protocol`/`Renderer` construct and `Protocol.encode_ready()` runs correctly under real MicroPython v1.24.0 (byte-identical shape to the earlier CPython check, which itself passed all 8 lines of `contracts/laptop_to_pico.v2.jsonl`). `NullDisplayDriver` stands in for the real ST7735S driver until M16. Still open: running `main.py`'s full loop against a real (or fake) laptop peer to prove the handshake/render/button/heartbeat cycle end-to-end, and confirming the USB stream stays clean without REPL interference. |

## Integration and MVP verification

References: [integration plan](hackathon_plan.md) and [acceptance checks](features_and_goals.md).

| Owner | Status | ID | Task / completion check | Needs | Notes |
| --- | --- | --- | --- | --- | --- |
| — | [ ] Todo | M18 | Wire laptop coordinator/scheduler and entry point: button → decision → saved event → view; due completion precedes controls. | M06–M09, M11–M14 | Build a minimal vertical slice early using fakes, then fill out the flow. |
| — | [ ] Todo | M19 | Verify restart, system-sleep, storage-failure and shutdown handling; unfinished timers end neutrally and pending breaks survive. | M18 | Saved elapsed lower bounds and no replayed animations. |
| — | [ ] Todo | M20 | Run full fake-device MVP scenarios and type checks; fix failures and record results. | M10, M18, M19 | Includes pause exclusion, stale control epoch, duplicate completion, and portable not-found/unique/ambiguous serial discovery. |
| — | [ ] Todo | M21 | Run real-device acceptance checks; verify readable screens, feeding, timers and reconnect; fill the Pico performance table and identify the measured bottleneck. | M17–M19 | Record line size, decode/validation time, display time, memory change/GC spikes and button-to-render latency. Optimize or change JSON only from this evidence. |
| — | [ ] Todo | M22 | Document actual setup/run/flash/report commands and demo steps; reconcile docs with implemented interfaces. | M10, M20, M21, M23 | Document dev/hardware profile commands, Windows deployment and portable port discovery; no invented commands or blanket completion of unverified tasks. |

Existing hardware progress does not make an entire firmware task complete. Record
verified substeps in Notes and check the row only when its full completion check
passes. Open tuning and post-MVP reward/layout choices remain in
[design_decisions.md](design_decisions.md), not additional tasks on this MVP board.
