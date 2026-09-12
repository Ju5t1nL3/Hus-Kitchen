# Laptop ↔ Pico protocol v1

Status: proposed contract; supersedes the unimplemented positional text commands
in the original AGENTS file. Both implementations must follow this document and
the same JSON fixtures. No laptop Python package needs to run on MicroPython.

## Framing and validation

- USB carries UTF-8 JSON objects, one per `\n`-terminated line. Examples below
  are literal individual messages; every line must end in a newline on the wire.
- Maximum encoded line: 2,048 bytes including newline. Reject oversized lines by
  discarding through the next newline, then resume parsing. Do not keep growing a
  receive buffer. Accept optional `\r` before `\n`.
- Every message has `v: 1` and a `type` string. Validate required fields, enum
  values, ranges, and JSON types (a boolean is not an integer). No NaN/infinity.
- Connection and boot IDs are nonempty printable ASCII strings up to 64 characters
  (except the null boot-ready connection ID). Animation IDs allow up to 96.
  Ping/pong nonces are nonnegative integers. Button lists contain unique IDs and
  must advertise the baseline buttons 1 and 2, optionally 3.
- Invalid JSON, incomplete messages, unknown message types and invalid values
  produce no game action. Unknown extra object fields may be ignored.
- Unsupported protocol version or UI vocabulary prevents gameplay handshake.
  Show a local firmware/laptop compatibility diagnostic; do not guess a schema.
- A malformed render does not partially update the display. Keep the previous
  valid view. Discard incomplete lines on disconnect. Only the laptop decides
  game outcomes; protocol validation on the Pico is permitted device behavior.
- Poll/read available bytes into a bounded line buffer. Do not let a partial line
  block firmware buttons. Laptop serial reads run in a dedicated worker; firmware
  runs a cooperative nonblocking loop. Serial port/baud selection is adapter
  configuration, not part of the message format.
- Application logging must not share this protocol stream.

## Pico → laptop: exactly three message types

### `ready`

On boot, the Pico announces itself with a null connection ID. The laptop sends a
`hello` whenever it opens/reopens a port, including when it missed the boot line.
The Pico answers each hello with the supplied connection ID.

```json
{"v":1,"type":"ready","connection_id":null,"boot_id":"boot-a1","buttons":[1,2],"ui":"pet_v1"}
{"v":1,"type":"ready","connection_id":"link-001","boot_id":"boot-a1","buttons":[1,2],"ui":"pet_v1"}
```

`boot_id` is an opaque identifier regenerated at firmware boot and retained for
that boot. Its random-generation details depend on the board; correctness relies
on the laptop-generated unique connection ID, not boot-ID uniqueness alone.
`buttons` lists implemented physical IDs: `[1,2]` or `[1,2,3]`. `ui: pet_v1`
advertises the required mood/menu/animation/asset vocabulary below.

### `button`

```json
{"v":1,"type":"button","connection_id":"link-001","boot_id":"boot-a1","seq":1,"button":1,"action":"press"}
{"v":1,"type":"button","connection_id":"link-001","boot_id":"boot-a1","seq":2,"button":2,"action":"hold"}
```

| Field | Contract |
| --- | --- |
| `connection_id` | Current non-null ID supplied by laptop hello |
| `boot_id` | Same as the matched ready response |
| `seq` | Positive integer, increases for each emitted button event; resets to 1 after a new hello |
| `button` | Physical ID advertised in `ready`, not a semantic menu action |
| `action` | Exactly `press` or `hold` |

Proposed hardware settings: 20 ms debounce and 600 ms hold threshold, configurable
in firmware. A short press emits once when stably released. A hold emits once
when its threshold is reached, with no press on release and no repeated holds.
Use wrap-safe MicroPython tick comparisons. On boot/new hello/disconnection,
require currently held buttons to be released before accepting a fresh gesture.

The laptop accepts only messages matching the current connection and boot, after
a matching ready. Reject `seq <= last_accepted_seq`; gaps are allowed, never
fabricated into missing actions. The Pico does not retry button messages. A lost
gesture during disconnect requires a new press; it must not become a delayed
purchase after reconnect. Queued inputs retain their connection ID so the
application can reject them even if they were parsed before a disconnect.

### `pong`

```json
{"v":1,"type":"pong","connection_id":"link-001","nonce":7}
```

Echo the nonce of a valid current-session ping. It reports transport liveness,
not a successfully drawn frame, a button acknowledgement, or focus completion.

**The Pico never sends hunger, health, coins, clock time, elapsed focus time,
`feed`, `buy`, `focus_complete`, rewards, or event-log entries.** A gesture is the
only gameplay input. The laptop knows the current menu and resolves its meaning.

## Laptop → Pico

### Connection and heartbeat

```json
{"v":1,"type":"hello","connection_id":"link-001"}
{"v":1,"type":"ping","connection_id":"link-001","nonce":7}
```

`hello` establishes a fresh opaque laptop-generated ID (UUID in implementation).
On each hello the Pico clears pending animations, resets message/button sequence
tracking, discards old UI session data and responds with ready. Only apply other
messages matching the accepted ID. Handshake retries use a fresh ID, so a
delayed earlier response cannot reset the current laptop's input sequence.
Keep the connection overlay visible until the first valid render in that session.

The laptop proposes ping every 2 seconds and a 6-second timeout. Pico uses a
6-second stale-input timeout for the v1 baseline; changing timing must keep both
ends compatible. Any valid current-session laptop message refreshes its watchdog.
On timeout show a neutral “Connect laptop” overlay and hide the stale countdown;
suppress gestures/animations until a fresh hello. This is connection UI, not a
change to pet mood or focus state. The laptop declares a failed heartbeat if no
matching pong arrives within the configured timeout and reconnects with a new ID.

### `render`: complete screen snapshot

```json
{"v":1,"type":"render","connection_id":"link-001","revision":1,"view":{"mode":"clock","mood":"happy","clock_text":"14:32","timer_seconds":null,"progress_stage":null,"stats":null,"coins":null,"menu":null,"accessory":null,"feedback":null}}
{"v":1,"type":"render","connection_id":"link-001","revision":2,"view":{"mode":"menu","mood":"happy","clock_text":"14:32","timer_seconds":null,"progress_stage":null,"stats":null,"coins":20,"menu":{"id":"feed_premium","label":"Premium food","cost":5,"enabled":true},"accessory":null,"feedback":null}}
{"v":1,"type":"render","connection_id":"link-001","revision":3,"view":{"mode":"pomodoro","mood":"focused","clock_text":"14:32","timer_seconds":1499,"progress_stage":0,"stats":null,"coins":null,"menu":null,"accessory":"accessory_01","feedback":null}}
{"v":1,"type":"render","connection_id":"link-001","revision":4,"view":{"mode":"menu","mood":"sad","clock_text":"14:33","timer_seconds":null,"progress_stage":null,"stats":{"hunger":20,"friendship":65,"health":90,"streak":3},"coins":20,"menu":{"id":"stats","label":"Pet stats","cost":null,"enabled":true},"accessory":null,"feedback":null}}
```

| Field | Type / limits | Meaning |
| --- | --- | --- |
| `revision` | Positive increasing integer per connection | Ignore stale/duplicate revisions; gaps are allowed |
| `mode` | `clock`, `menu`, `pomodoro` | Draw this layout |
| `mood` | `happy`, `sad`, `sick`, `focused` | Laptop-selected pose; sick takes precedence over focus pose |
| `clock_text` | Exactly `HH:MM`, valid 24-hour time | Draw literally; no local timezone/clock calculations |
| `timer_seconds` | Integer 0–86,400 or null | Required non-null only in pomodoro; format as minutes/seconds, do not decrement locally |
| `progress_stage` | Integer 0–8 or null | Non-null only in pomodoro; draw selected art, do not calculate progress |
| `stats` | Object with integer `hunger`, `friendship`, `health` 0–100 and nonnegative integer `streak`, or null | Non-null only in menu with selected `stats`; null means hide |
| `coins` | Nonnegative integer or null | Non-null in menu only; no arithmetic on firmware |
| `menu` | `{id, label, cost, enabled}` or null | Non-null in menu only |
| `menu.id` | One of IDs in MVP goals | Presentation identity; never acted on locally |
| `menu.label` | Printable ASCII, 1–24 characters | Laptop-provided display label; bounded for font/layout |
| `menu.cost` | Nonnegative integer or null | Show price only when supplied; basic food may show zero |
| `menu.enabled` | Boolean | Draw enabled/disabled styling; still send physical button presses |
| `accessory` | `accessory_01` or null | Asset to draw; ownership already checked on laptop |
| `feedback` | `fed`, `trick`, `purchased`, `equipped`, `removed`, `insufficient_coins`, `unavailable`, `cancelled`, `storage_error`, or null | Transient text/icon, cleared by a later snapshot |

All view keys are required, using null for absent content. Reject inconsistent
combinations rather than retain prior field values. Validate the entire object,
then swap the desired view atomically in RAM. LCD painting may still take time;
this contract does not promise a hardware double buffer or instantaneous redraw.
The stats menu requires a non-null stats object; every other menu entry requires
null stats. The completion view uses pomodoro mode, zero seconds and stage 8 even
though the laptop has already committed completion and cleared its active session.

Snapshots are sent on connection, after accepted actions/UI changes, and when a
visible clock/timer/progress value changes. A full snapshot is small enough for
MVP; avoid diff protocols until measured bandwidth justifies one.

### `animate`: transient presentation cue

```json
{"v":1,"type":"animate","connection_id":"link-001","animation_id":"event-uuid:feed","after_revision":5,"name":"feed"}
```

`name` is `feed`, `coin_rain`, `trick`, or `wake_up`. `animation_id` derives from
the committed event ID plus cue name; it is not another gameplay event.
`after_revision` requires an applied snapshot at least this new. The laptop writer
sends an adequate snapshot before the cue; if it coalesces to a newer snapshot,
that newer revision satisfies the prerequisite. Drop an early cue rather than
blocking firmware waiting for a missing snapshot.

Use a small recent-ID cache (proposed 32 entries) to suppress immediate duplicates;
this is not permanent deduplication. Playback is best effort, never retried after
reconnect/restart. New render snapshots remain authoritative during animation.
Animations cannot obscure the sick pose or starve button/serial polling. When
overloaded, discard older cues and retain the newest screen state.

## Example end-to-end action

1. Laptop sends hello; Pico answers ready with that ID.
2. Laptop renders the clock. Pico button 1 press arrives; laptop opens the menu.
3. Pico button 2 press arrives while `start_focus` is selected. Laptop persists
   `focus_started`, creates its runtime deadline, and renders the focus view.
4. Laptop reaches the deadline, persists `focus_completed` including rewards,
   renders the completed view, and issues `coin_rain`.
5. After the configured brief completion display, the laptop sends the clock view.

No firmware change is needed to adjust food prices, focus rewards, button
mappings, mood thresholds, or decay. New asset/menu vocabularies or incompatible
message shapes require coordinated UI/protocol version changes and fixtures.
