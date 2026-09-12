# Hackathon coordination and implementation plan

There are four team members; possibly only two will work on software. Nobody is
assigned a role or module in advance. Pick an available task from
[todo.md](todo.md), claim it, and keep its status current.

## Task-based coordination

Ownership lasts for the claimed task, not an entire folder. Its claimant coordinates
shared-file edits with anyone working on related tasks. Record affected shared
files and handoffs in the board's Notes column; do not silently take another claim.

Core records, config, dependency/checker settings and shared fixtures need particular
coordination. Agree on one writer for each overlapping change at that time, without
assigning a permanent integration role. Keep feature tests in separate files rather
than a shared test_everything.py. The board owns statuses; this document owns the
integration sequence and verification guidance.

## Agree before splitting branches

Freeze typed command/event/result records, protocol v2/UI emotions_v1, and the
screen controls. Use [class design](class_design.md) and
[implementation guidelines](implementation_guidelines.md). Whoever claims the
bootstrap/contracts tasks creates the minimum shared definitions and checker setup,
coordinating interfaces with their consumers. No generic framework or unused
future modules are required.

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

1. Inspect and document the board setup already done; reuse working wiring,
   firmware and assets. The laptop uses CPython 3.14 with tooling under `laptop/`.
   Bootstrap shared contracts and draw home/setup/timer examples; start USB and
   fake-device paths as their inputs become available.
2. Connect one end-to-end focus start → countdown → saved completion → break offer.
3. Pick remaining tasks for pause/resume/end, feeding/emotions, reports/recovery,
   artwork/screens, controls, breaks and reconnect. Independent work can proceed
   against fakes; the board records who is doing each piece.
4. Run acceptance scenarios on the actual device, then tune readability/reactions.
5. Only after MVP works, select a backlog feature if time permits.
   The next planned milestone is [XP/coins/levels](progression_design.md), followed
   by keyboard and head-tracking bonuses in the [roadmap order](nice_to_haves.md).

Accelerate a fake clock to exercise long sessions quickly. A test harness can
advance time while retaining the real 5–60-minute choices and grace calculation;
do not add an undocumented seconds-mode shortcut to production firmware.

## Integration practices

- Claim tasks before editing, use a branch/worktree per task if useful, and
  integrate small working changes early. No automatic branches or role assignments.
- Coordinate shared type/config/dispatch edits with current task claimants.
- Avoid sweeping renames/reformatting during parallel work.
- A contract change updates producer, consumer, examples and owning docs together.
- Fake hardware lets rules/app work proceed before wiring; recorded views let
  firmware/art proceed before game logic is complete.
- Folder boundaries reduce merge conflicts but do not replace communication.

## Essential verification

| Boundary | Checks |
| --- | --- |
| Controls/UI | Every two-button action, setup wrap/default/remembering, paused labels, no automatic break start |
| Control modularity | Remap an action and simulate a third button through the same path; matching labels; invalid bindings rejected; no timer-rule edits |
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
