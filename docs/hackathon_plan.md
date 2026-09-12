# Hackathon ownership and implementation plan

Goal: let teammates implement independently against stable contracts. No folder
layout guarantees zero conflicts, but clear ownership prevents routine collisions.
Four areas below are suggested roles, not an assumption about team size or a
request to launch autonomous agents. One person can own several areas.

## Ownership

| Area | Owns files | Depends on | Independent demo |
| --- | --- | --- | --- |
| A — game rules | `features/pet.py`, `focus.py`, `shop.py`, `replay.py`, `tests/domain/` | Core types and event schema | Feed, complete focus and replay a sample history without hardware |
| B — persistence and history | `adapters/sqlite_event_store.py`, `features/history.py`, `adapters/text_report.py`, `tests/storage/` | Event envelope and store port | Append/reopen/deduplicate events; print weekly recap |
| C — firmware and art | All `pico/`, `tests/firmware/` | Wire spec + fixtures, hardware inventory | Draw fixture screens and emit debounced gestures over USB |
| D — app and laptop transport | `app/`, serial/clock/config/fake adapters, `tests/app/`, `main.py` | Core ports, feature signatures and wire spec | Drive fake device from a scripted button sequence |

One designated integration owner (initially D) owns shared changes to `core/`,
`config.yaml`, `pyproject.toml`, dependency lockfiles, shared test setup,
`tests/contracts/`, AGENTS, and cross-cutting design documents. Owners propose
contract changes to that person before callers/callees diverge. Avoid each teammate
adding dependencies, menu entries or fixtures to the same central file independently.

Feature-specific test files and docs can be split further if two people need to
work in the same area. Avoid a single shared `test_everything.py` or `utils.py`.

## Freeze the first contracts together

Before parallel implementation, agree on the current signatures, event names,
protocol v1 and UI vocabulary. The integration owner creates a small compilable
core contract skeleton and commits shared fixtures before feature branches split.
This is the only necessary shared bootstrap; do not build a framework first.

Include concrete shared record/union definitions and a configured laptop static
type checker in that bootstrap, following the
[implementation guidelines](implementation_guidelines.md).

Required initial fixture set:

- Boot ready, hello/ready exchange, press, hold, pong, clock/menu/stats/focus views,
  completion frame, animation, malformed input and unknown-version messages.
- Golden event sequence: initialize → start → complete → feed → buy → equip,
  with expected final state and expected report. Include explicit timestamp,
  timezone, session terms and resolved effects.
- Fake clock/device/store implementing the same public ports as real adapters.

MicroPython and laptop implementations share fixtures/specification, not a forced
shared package that pulls CPython dependencies into firmware. Fixture changes are
reviewed as API changes by both owners.

## Delivery sequence

1. **Bootstrap contracts:** create packaging/config skeleton and the minimum types,
   fixtures and fake ports. Choose exact hardware driver during bring-up.
2. **First vertical slice:** Pico/fake button → app → `focus_started` in SQLite →
   focus render. Complete a short demo session → exactly one reward → celebration.
3. **Independent expansion:** A finishes care/shop/replay; B completes reports and
   persistence recovery; C finishes art/menu/driver; D finishes controls, reconnect
   and suspend/deadline behavior. Integrate small changes frequently.
4. **MVP hardening:** run the acceptance scenarios below and tune configuration/art.
5. **Only then extend:** select one backlog feature if time permits, preferably a
   GitHub input adapter that reuses the commit/reward/presentation path.

Do not make a firmware teammate wait for real gameplay data: recorded valid views
are enough. Do not make a rules teammate wait for a device: typed commands and
fake clocks are enough. Do not make reports depend on Pico connectivity.

## Branch and merge practices

- Agree on named ownership and use one branch/worktree per area if useful. These
  docs do not create branches or assign teammates automatically.
- Avoid broad reformatting and file renames while parallel work is in flight.
- Keep `main.py` a composition root so features do not all need to edit it.
- The integration owner makes dispatch/config additions once, after interfaces
  are agreed, or queues those edits in small sequential commits.
- Update from the integration branch frequently and merge a working vertical slice
  early. A type/interface mismatch is an integration issue even without git conflicts.
- A contract change includes producer, consumer, fixture and documentation changes.
  Coordinate a single landing point rather than shipping half of a wire change.

## Verification gates

These are implementation acceptance checks, not tests already run in this repo.
Prefer targeted behavioral checks; do not write tests that merely mirror methods.

| Boundary | Essential checks |
| --- | --- |
| Feature rules | Bounds, unaffordable/repeated purchase, free recovery, no duplicate session completion |
| Replay/storage | Rebuilt state equals incremental state; config edits do not change past effects; commit-before-display crash; duplicate terminal key; unknown/corrupt event stops startup |
| Time/history | Deadline/cancel tie; midnight and timezone credit; today/yesterday streak; suspend gap before completion; no offline decay |
| Protocol | Fragmented/combined lines, oversize discard, malformed types, stale connection/sequence/revision, reconnect to already-booted Pico |
| Firmware | Bounce, short press vs hold exclusivity, held button on reconnect, rendering during USB traffic, nonblocking animations |
| Application | Fake button → event → render; USB disconnect does not stop focus; storage failure cannot grant reward; completion display expires |
| Hardware demo | Cold boot, real button responsiveness, readable countdown, always-visible sick pose, unplug/replug, measured LCD refresh |

Use a short configured demo duration; never modify firmware or hardcode a shortcut
that bypasses completion rules. Document the measured gesture recognition, laptop
processing and LCD repaint times separately before claiming the latency target.

## MVP done

All acceptance criteria in [features_and_goals.md](features_and_goals.md) pass,
the team can run the laptop/firmware from documented commands, hardware choices
are recorded, and the canonical docs match actual interfaces. Add setup/run
instructions once implementation provides real commands; do not invent working
commands in advance.
