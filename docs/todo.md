# Expanded MVP task board

This is the source of truth for task ownership and progress. There are four team
members, but possibly only two working on software. Anyone can claim an available
task; there are no assigned people, permanent roles or department ownership.

This board now includes the user-approved progression expansion that must land
before final MVP verification. Unlisted future ideas remain inactive.

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
| — | [ ] Todo | M10 | Implement focus-chain and daily-streak queries plus the weekly text recap; pauses/breaks are excluded, cumulative samples are not double counted, and the first qualifying completion of a streak day is identifiable for M30. | M08, M09, M29 | Do this alongside the daily-streak reward work. Exact focus-chain reset and daily bonus rules remain a user choice; this task supplies tested facts rather than awarding yarn. |
| justinle2006 | [x] Done | M11 | Implement validated configuration, action definitions and button bindings; remapping changes behavior and labels together. | M04, M05 | Added typed YAML config, canonical actions, validation, resolution, navigation and generic third-button support. Remapping drives behavior and labels together; Ruff, strict Pyright and all 75 tests pass. |
| liannie3 | [x] Done | M12 | Implement screen presenter for Home/setup/focus/paused/break offer/break; snapshots match the wire contract. | M06, M07, M11 | Implemented `app/presenter.py` (`build`/`on_commit`) and `features/emotions.py` (`select`, per event_model.md). `tests/app/test_presenter.py` reconstructs all 7 independent screen fixtures from serial_protocol.md and asserts exact RenderSnapshot field equality, plus on_commit navigation/cue cases (session start, focus completion, feed, break). `uv run ruff check`, `uv run ruff format` and `uv run pyright` all pass; `python -m unittest discover -s tests` is 42/42 green (installed `uv` locally via pip since it wasn't on PATH here; also added `tzdata` as a Windows dependency in pyproject.toml since `zoneinfo` has no tz database on Windows without it, which was failing even the pre-existing M06 timer tests). Added a minimal `app/controls.py::labels()` (press/hold/unbound resolution only, no validation/resolve/navigate) as a stand-in for M11's real bindings loader — presenter's tests build their own fixture bindings/actions, not real config, so this is not yet exercised against actual M11 output. `on_commit`'s PetFed branch is tested against a synthetic event, not yet wired to `features/feeding.py::decide` (now done by M07) end-to-end. **Reworked for the three-button redesign** (docs/features_and_goals.md, docs/serial_protocol.md, docs/class_design.md, docs/event_model.md): removed `ControlContext.BREAK_PAUSED` and the `BreakSessionPaused`/`BreakSessionResumed` event types (break can no longer pause — `features/timers.py` now rejects `PauseSession`/`ResumeSession` for break-kind sessions with `Rejected(UNAVAILABLE)`); added `RuntimeState.clock_reveal_until_mono_ms` and presenter.build's clock-reveal projection (Time button swaps the countdown for real HH:MM for 5s, pure function of `now` vs that deadline, no scheduler change needed); added `ActionId`/`ControlIntent` `ShowTime` and `RestartFocus` plus `ActionId.END_BREAK` (reuses the `EndCurrent` intent under the "Home" label for break_running). `tests/app/test_presenter.py` and `tests/features/test_timers.py` updated/added for the new bindings, labels and rejection; `contracts/laptop_to_pico.v2.jsonl` updated to the real 3-button layout including a clock-reveal fixture. Fixed a pre-existing Python-2-style `except json.JSONDecodeError, ValueError:` syntax error in `adapters/wire_codec.py` (would have failed to import). All 55 tests, ruff and pyright pass. Superseded by justinle2006's M11 completion (config-driven bindings loader, `controls.resolve`/`controls.navigate`, startup validation), merged in cc8b9c6. |
| justinle2006 | [x] Done | M13 | Implement laptop wire codec; fragmented, combined, invalid and oversized messages behave as specified. | M04, M05 | Added incremental bounded framing, strict protocol-v2 validation, complete-view/declared-button checks and exact compact fixture encoding. Ruff, strict Pyright and all 96 tests pass. |
| justinle2006 | [x] Done | M14 | Implement portable serial discovery plus the threaded USB link, bounded queues, heartbeat and reconnect; latest view restores and stale input is discarded. | M13 | Added deterministic metadata/port resolution, pyserial adapter, reconnecting reader/pump workers, atomic writes, handshake and heartbeat validation, latest-view restoration, bounded/coalesced output, and stale-input rejection. Windows/POSIX fake coverage; 108 tests plus Ruff and strict Pyright pass. |

## Developer simulator

Reference: [development and hardware modes](development_modes.md).

| Owner | Status | ID | Task / completion check | Needs | Notes |
| --- | --- | --- | --- | --- | --- |
| justinle2006 | [x] Done | M23 | Implement explicit `dev`/`hardware` composition profiles and a clickable virtual Pico with screen, dynamic buttons, fake-time controls and bounded bidirectional JSON trace; a full focus/break flow and invalid/reconnect cases traverse the production codec. | M11–M14, M18 | Added explicit profiles, temporary dev SQLite, loopback browser UI, protocol-validating virtual Pico, controllable time and bounded trace. Full focus/Time/pause/resume/break, malformed/oversized/stale and reconnect cases traverse the serial link/codec. Hands-on fixes keep buttons stable across polling, show focus/break minutes on Setup and preserve manual trace scrolling. Actual loopback state API, Ruff, strict Pyright, CLI help and all 131 tests pass. |

## Progression and expanded feeding

References: [progression and economy](progression_design.md), [product behavior](features_and_goals.md), [events](event_model.md).

Complete these in order. Values explicitly marked open require a user decision;
do not bury guessed rates in code.

| Owner | Status | ID | Task / completion check | Needs | Notes |
| --- | --- | --- | --- | --- | --- |
| justinle2006 | [x] Done | M24 | Add the progression/economy foundation: durable XP, level and yarn balance; validated policy types/config; versioned events and deterministic replay; render-contract fields for the top strip. Restart/retry cannot duplicate or recalculate recorded changes. | M08, M09, M12, M18, user foundation choices | Added validated progression config/state, one-time versioned initialization with deterministic replay/SQLite round-trip, and Home-only typed JSON/simulator strip. Provisional 10 yarn/100 XP remain configurable; M27 owns focus payouts. Ruff, strict Pyright and all 132 tests pass. |
| justinle2006 | [x] Done | M25 | Replace immediate free Feed with a Feed menu offering Food, Drink and Back; Food/Drink each show a configured yarn cost, atomically spend yarn and feed the pet, and reject insufficient funds without changing state. | M24, M11–M13, user item choices | Added Jollof Rice (3 yarn), Coffee (2), Back, atomic purchase/feed events, affordability labels/rejections, 30-second Happy, shared configurable feed animation, replay/SQLite/wire/dev-simulator coverage. M16/M17 still own physical assets/rendering. Ruff, strict Pyright and all 138 tests pass. |
| justinle2006 | [x] Done | M26 | Define and implement the complete mood catalog, precedence, triggering events and durations; update typed mood/render contracts, rules, fixtures and sprites together. | M25, user mood specification | Implemented Idle, Happy (15s), persistent Sad + 5 runtime Pet taps, persistent five-minute Hungry, Working Neutral/Sad hook, Sleeping, Party, precedence and durable feed/comfort timing. Feed works in Idle/Happy/Hungry and resets hunger; Sad blocks it. Added nullable M27 reward view. M16/M17 retain physical PNG/firmware rendering. Ruff, strict Pyright and all 138 tests pass. |
| justinle2006 | [x] Done | M27 | Decide and implement base XP and yarn gains from completed focus sessions using a versioned policy and one durable, deduplicated reward breakdown per completion. | M24, M26, user reward choices | Added approved integer reward/chain formulas, uncapped increasing level curve, resolved durable reward events, replay/SQLite validation, runtime chain resets, Party earnings and dev XP diagnostics. Ruff, strict Pyright, all 142 tests and CLI help pass. |
| justinle2006 | [x] Done | M28 | Add optional keystroke-count summaries and their additional yarn calculation; count activity only during active focus, never capture keys/text, and verify pause exclusion and opt-out. | M27, user keyboard reward choices | Added persistent opt-in Settings, active/unpaused count-only pynput tracking and capped 0–2 yarn with no XP. Fixed the observed macOS race by waiting for listener readiness before checking trust; regression test reproduces the old false-unavailable timing. Ruff, strict Pyright and all 150 tests pass. |
| justinle2006 | [x] Done | M29 | Add optional local camera-attention summaries and their additional yarn calculation; store no frames/identity, distinguish unavailable observations, and verify pause exclusion and opt-out. | M28, user attention reward choices | Added an OS-agnostic OpenCV Haar adapter, independent persisted opt-in, active/unpaused sampling, five-second Working Sad signal, unknown-frame handling and capped +1/+2 yarn at 70%/90% attention with 60% coverage. No frames/identity or camera XP. Ruff, strict Pyright and all 154 tests pass. |
| — | [ ] Todo | M30 | Add yarn bonuses for crossed levels and the first qualifying completion on a continuing daily streak; extend the explainable deduplicated breakdown and test day boundaries and multi-level gains. | M10, M24, M27–M29, user bonus/streak choices | M27 already owns the approved focus-chain XP/yarn scaling and resets. Level/daily amounts remain open; no bonus may be granted twice after restart. |

## Device firmware and artwork

References: [components](components.md), [serial protocol](serial_protocol.md)
and the [TinyScreen+ hardware record](../tinyscreen/README.md).

**Hardware change:** the device is now a TinyCircuits TinyScreen+ running
C++/Arduino, not a Raspberry Pi Pico running MicroPython. The Pico's external SPI
LCD never worked reliably (see the retained [pico/README.md](../pico/README.md)
for that trail); the TinyScreen+ integrates its display and four buttons on one
board. Firmware lives in `tinyscreen/firmware/`. The rows below were rewritten
for that hardware; their MicroPython-specific completion checks no longer apply.

| Owner | Status | ID | Task / completion check | Needs | Notes |
| --- | --- | --- | --- | --- | --- |
| liannie3 (AI) | [x] Done | M01 | Inventory all project-relevant board capabilities and existing work — MCU, memory, USB, buttons, display, bus, driver, timing, JSON, reset, scheduling and expansion — and pin the exact firmware toolchain. | Existing hardware | Superseded Pico work: RP2040 with a 128x160 ST7735S SPI TFT, buttons on GPIO10/11, display never reliable. **Current hardware inventoried in [tinyscreen/README.md](../tinyscreen/README.md)**: TinyScreen+, ATSAMD21G18A, 256KB flash / 32KB RAM, built-in 96x64 SSD1331 OLED, four corner buttons (core pins 19/25/30/31, active-low pull-up), native USB CDC `0x03EB`/`0x8009`, plus a stacked MicroSD/Audio TinyShield (DAC on `A0` working, microSD empty). Toolchain pinned: `arduino-cli` 1.5.1, `TinyCircuits:samd` 1.1.0, FQBN `TinyCircuits:samd:tinyscreen`, `TinyScreen` 1.1.0 and `ArduinoJson` 7.4.3. Recorded the `Serial` vs `SerialUSB` trap that silently breaks all protocol I/O on this core. |
| liannie3 (AI) | [x] Done | M15 | Complete/verify hardware configuration and generic button scanning; clean press-or-hold events carry declared IDs/epochs. | M01, M05 | `hardware_config.h`/`buttons.cpp` define all four corner buttons as a table the scanner iterates; no per-button branches. On-device: each of the four buttons produces a clean `press` gesture carrying the correct ID and the latched control epoch, observed arriving at a host over USB. Debounce 20 ms and hold 600 ms match the protocol doc. Still open: a physical hold-gesture test (the code path exists and suppresses the trailing press, but was never exercised by hand) and rapid-press chatter tolerance. |
| liannie3 | [ ] Doing | M16 | Create/verify device layouts and sprites: full pet, small-face moods, food, feeding and celebration; drawing remains responsive. | M01, M05 | Canvas is **96x64**, not the previously planned 128x160. Implemented so far: 2-frame poses for Idle/Happy/Sad/Working Neutral, a single-frame Working Sad, dedicated single poses for break_offer (party) and the running break screen (a small 24x24 face, top-center), plus corner button icons (hourglass for Focus, pizza for Feed, a gear for Settings, up/down carets, a food icon for the Jollof item, and the yarn currency badge), all converted from PNG sources in `tinyscreen/sprites/` to BGR332 arrays. Any mood without dedicated art (Hungry, Sleeping) falls back to Idle rather than failing to draw, matching the protocol's "accept every documented value" rule. Sleep1/2 exist as source PNGs but are intentionally not wired up yet -- see nice_to_haves.md's idle-triggered-sleep idea (#11), which needs a product decision on the idle-timer/mood-precedence interaction before it's implemented. Still open: eating/food-consumption animation frames (eat1-3 exist but aren't wired to a trigger), a Coffee/Drink icon (no source art yet), and the responsiveness measurement, which belongs with M21. Flash is at 83% with the current asset set (audio dominates); further art needs a size check. |
| liannie3 (AI) | [ ] Doing | M17 | Integrate firmware codec/main loop, buttons and rendering; handshake, disconnect overlay and recorded views work on the device. | M15, M16 | Unblocked by the board change — the Pico display fault that blocked this is gone. `protocol.cpp` ports the MicroPython validator to C++/ArduinoJson and `firmware.ino` runs the cooperative loop. Verified on-device against a host harness: `hello` → `ready` (advertising `[1,2,3,4]`), `ping` → `pong`, physical presses arriving as `button` messages, and laptop-sent views driving every screen. Still open: the disconnect/heartbeat-timeout overlay, animation cue playback, and running against the real `laptop/main.py --profile hardware` rather than the harness. |
| liannie3 (AI) | [x] Done | M31 | Support the device's four buttons end to end on the laptop: raise `ui.max_buttons`, bind buttons 3-4 where the corner layout calls for it, add reverse-cycle actions for setup/settings, point device discovery at the TinyScreen+ USB identity, and update the shared fixtures and simulator to four buttons. | M11, M13, M23 | Added `CycleDurationBack`/`CycleSettingBack` intents+actions ("Down"), `ui.max_buttons: 4`, `device.usb_vid/usb_pid` pointed at `0x03EB`/`0x8009`, and bound buttons 3-4: Settings (button 3, replacing the old hold-button-1 gesture -- a gear icon on the device) and Pet (button 4) on Home; Down (button 3) and Back (button 4) on setup/settings. Buttons 1-2 keep their three-button-era meanings unchanged everywhere. Updated `contracts/*.jsonl`, the simulator's default button set and every affected test. Verified against clean `HEAD`: same 2 pre-existing environment-only failures (missing `cv2`, a Windows file-lock test), zero regressions from this change; Ruff clean. |
| liannie3 (AI) | [ ] Doing | M32 | Bring the C++ firmware into exact agreement with the wire contract: accept the full mood vocabulary and every screen, parse `progression`, `earned_rewards` and `settings`, and replay the shared fixtures as a firmware test. | M17, M31 | Done: mood whitelist now matches the M26 catalog (was still the pre-M26 6-value list, which would have rejected every real laptop render), screen list covers all 7, `earned_rewards` is parsed and shown on the focus-complete screen. Still open: `tinyscreen/tests/test_protocol.cpp` (a host-compiled build of the real `protocol.cpp` against a minimal Arduino shim, replaying `contracts/laptop_to_pico.v2.jsonl`) is written but not yet built/run -- finish that to actually prove fixture agreement rather than relying on manual review. |

## Integration and MVP verification

References: [integration plan](hackathon_plan.md) and [acceptance checks](features_and_goals.md).

| Owner | Status | ID | Task / completion check | Needs | Notes |
| --- | --- | --- | --- | --- | --- |
| justinle2006 | [x] Done | M18 | Wire laptop coordinator/scheduler and entry point: button → decision → saved event → view; due completion precedes controls. | M06–M09, M11–M14 | Added the single-writer coordinator, pure timer sampling/wake scheduling, system-clock and hardware composition adapters, and CLI entry point. Fake-device flows cover three-button navigation, save-before-render/cue, focus pause/resume, Time expiry, Again's two-event transition, completion-before-stale-End, and reconnect revisions. Ruff, strict Pyright, all 120 tests and the CLI help smoke check pass. |
| justinle2006 | [x] Done | M19 | Verify restart, system-sleep, storage-failure and shutdown handling; unfinished timers end neutrally and pending breaks survive. | M18 | Added neutral restart/suspend/storage-recovery/shutdown endings, persisted lower-bound recovery, pending-break restoration, storage-error freeze/replay feedback, and no replayed cues. Ruff, strict Pyright and all 125 tests pass. |
| — | [ ] Todo | M20 | Run full fake-device expanded-MVP scenarios and type checks; fix failures and record results. | M18, M19, M23–M30 | Includes economy/reward deduplication and opt-outs as well as pause exclusion, stale control epochs, duplicate completion and portable serial discovery. |
| — | [ ] Todo | M21 | Run real-device acceptance checks; verify readable progression/feed screens, timers and reconnect; fill the Pico performance table and identify the measured bottleneck. | M17, M19, M20 | Record line size, decode/validation time, display time, memory change/GC spikes and button-to-render latency. Optimize or change JSON only from this evidence. |
| — | [ ] Todo | M22 | Document actual setup/run/flash/report commands and demo steps; reconcile docs with implemented interfaces. | M20, M21 | Document dev/hardware profile commands, Windows deployment, privacy controls and portable port discovery; no invented commands or blanket completion of unverified tasks. |

Existing hardware progress does not make an entire firmware task complete. Record
verified substeps in Notes and check the row only when its full completion check
passes. Open tuning and layout choices remain in
[design_decisions.md](design_decisions.md) and the relevant task Notes.
