# Hackathon ownership and implementation plan

Agree on contracts, then build in separately owned files. Four areas are suggested
roles, not a required team size or permission to launch autonomous agents.

## Ownership

| Area | Owns | Independent demo |
| --- | --- | --- |
| A — rules | features/timers.py, feeding.py, emotions.py, replay.py; tests/domain rule/replay files | Start/pause/resume/end focus, derive a break and select emotions without hardware |
| B — storage/history | adapters/sqlite_event_store.py, features/history.py, adapters/text_report.py; tests/storage and history tests | Replay recorded sessions, enforce unique completion and print recap |
| C — Pico/art | pico/ and tests/firmware/ | Draw each screen/face/food fixture and report clean gestures |
| D — app/USB | app/, serial/clock/config/fake adapters, main.py and tests/app/ | Script two-button navigation against a fake device |

One integration owner (initially D) owns shared core records, config, dependency/
checker settings, shared test fixtures and cross-cutting docs. Feature-specific
tests have separate owners, even inside tests/domain. Avoid a shared utils.py or
test_everything.py that every teammate must edit.

## Agree before splitting branches

Freeze typed command/event/result records, protocol v2/UI emotions_v1, and the
screen controls. Use [class design](class_design.md) and
[implementation guidelines](implementation_guidelines.md). The integration owner
creates the minimum shared definitions and static-checker setup before branches
diverge. No generic framework or unused future modules are required.

Shared examples should include:

- Hello/ready, physical press/hold with control_epoch, heartbeat, each screen,
  paused focus/break, feed/celebration cues, malformed/stale input.
- A golden history: create → feed → focus start → pause → resume → complete →
  break start → end; expected projection, emotions and report.
- Separate grace/early-end histories and expected effects, including paused time.
- Fake device, clock and event store with the real ports' signatures.

Pico and laptop share contracts/examples, not a Python package that imports
laptop libraries into MicroPython.

## Build order

1. Bootstrap shared contracts, choose hardware/driver, and draw home/setup/timer
   examples. Start the real USB handshake and fake-device path.
2. Connect one end-to-end focus start → countdown → saved completion → break offer.
3. A finishes pause/resume/end, feeding and emotions; B finishes reports/recovery;
   C supplies small faces, food/animations and remaining screens; D connects
   controls, breaks, screen epochs and reconnect handling.
4. Run acceptance scenarios on the actual device, then tune readability/reactions.
5. Only after MVP works, select a backlog feature if time permits.

Accelerate a fake clock to exercise long sessions quickly. A test harness can
advance time while retaining the real 5–60-minute choices and grace calculation;
do not add an undocumented seconds-mode shortcut to production firmware.

## Integration practices

- Assign file ownership, use one branch/worktree per area if useful, and integrate
  small working changes early. This plan does not create branches automatically.
- Coordinate shared type/config/dispatch edits through the integration owner.
- Avoid sweeping renames/reformatting during parallel work.
- A contract change updates producer, consumer, examples and owning docs together.
- Fake hardware lets rules/app work proceed before wiring; recorded views let
  firmware/art proceed before game logic is complete.
- Folder boundaries reduce merge conflicts but do not replace communication.

## Essential verification

| Boundary | Checks |
| --- | --- |
| Controls/UI | Every two-button action, setup wrap/default/remembering, paused labels, no automatic break start |
| Timer | Multiple pause/resume segments, paused End, 59.999s vs 60s grace, deadline wins over End/Pause, break completion/end neutral |
| Emotion/feeding | One free food, correct assets, newest reaction wins, expiry does not revive older reactions, no hidden stats |
| Replay/storage | Incremental/rebuilt state match; duplicate/conflicting terminal and break-choice keys; pinned terms after config change; commit-before-render crash |
| History | No pause/break time credited as focus; cumulative samples not double counted; completion dates and today/yesterday streak |
| Recovery | Running/paused session interrupted neutrally; pending break restored; unsaved elapsed labeled unknown; no replayed animations |
| Wire/firmware | Fragmented/oversize/invalid JSON, stale seq/connection/epoch/revision, exclusive press/hold, nonblocking drawing and input |
| App/hardware | Old Pause cannot become Start break; disconnect doesn't stop timer; storage error freezes gameplay; readable screen and measured latency |

These are planned checks, not executed implementation tests. MVP is done when the
[product acceptance criteria](features_and_goals.md) pass, setup/run instructions
describe real commands, and hardware details and actual interfaces match the docs.
