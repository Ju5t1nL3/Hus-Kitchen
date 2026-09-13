# Laptop ↔ Pico protocol v2

Proposed JSON Lines contract for the emotion-only, three-button MVP. It replaces
the earlier unimplemented stats/shop v1 and an earlier two-button draft of this
plan. Require `v: 2` and UI `emotions_v1` on both ends; do not mix examples from
either former plan.

## Framing and connection

Each UTF-8 JSON object ends with newline. Maximum line size is 2,048 bytes including
newline; accept optional carriage return before it. Assemble available bytes
without blocking buttons. Discard oversized input through the next newline.
Validate types, required fields, enums and ranges; booleans are not integers.

Ignore unknown message types/extra fields; invalid known messages have no effect.
Unsupported version/UI prevents handshake. A render applies only after the whole
view validates. No REPL/debug printing may share the protocol stream.

Encode compact JSON with no optional whitespace. CPython and MicroPython encoders
should use `separators=(",", ":")` where supported. This protocol remains JSON
Lines: compact encoding does not remove the terminating newline. Both sides parse
and validate every received message before using it.

Connection/boot IDs are printable ASCII strings of 1–64 characters. The laptop
generates a new connection UUID whenever opening/retrying a connection. Boot ID
is an opaque Pico boot token; it is not a player identity. Sequence numbers,
revisions, epochs and nonces are integers as specified below.

## Pico → laptop: only ready, button, pong

```json
{"v":2,"type":"ready","connection_id":null,"boot_id":"boot-a1","buttons":[1,2],"ui":"emotions_v1"}
{"v":2,"type":"ready","connection_id":"link-001","boot_id":"boot-a1","buttons":[1,2],"ui":"emotions_v1"}
{"v":2,"type":"button","connection_id":"link-001","boot_id":"boot-a1","seq":1,"control_epoch":1,"button":1,"action":"press"}
{"v":2,"type":"pong","connection_id":"link-001","nonce":7}
```

| Message | Required behavior |
| --- | --- |
| ready | Announce once at boot with null connection ID; reply to each hello with its ID. Advertise configured physical IDs (default [1,2]) and UI emotions_v1. |
| button | Physical ID from ready.buttons; action press or hold; positive seq increasing within connection; positive control_epoch from the displayed view when the gesture began. |
| pong | Echo a valid current-session ping's nonnegative nonce. This checks liveness, not successful drawing or timer completion. |

ready.buttons contains 1–8 unique integer IDs in 1–255, in physical layout order.
The MVP advertises [1,2,3]. Adding an ID within these limits uses the same message
shape and needs no protocol version change. Reject input from unadvertised IDs.
Every render must include each advertised ID exactly once, even if unbound (label
"-", enabled false). The firmware hardware table supplies each ID's layout slot;
button count and actions are not inferred from a screen name. Home and the
break-running screen bind only two of the three IDs and render the third
unbound; every other screen binds all three.

Proposed debounce is 20 ms and hold threshold 600 ms, configured on Pico. A short
press emits once on stable release. Hold emits once at threshold, suppressing the
release press and further repeats. Use wrap-safe firmware tick comparisons.

Capture control_epoch when the button becomes stably down. This is presentation
metadata: Pico still does not know what the button means. If the laptop changes
screens while a gesture is in progress, the old epoch prevents that gesture from
activating a new action. The laptop validates epoch again at dispatch, after due
timer work, not only when parsing.

The laptop accepts button messages only after matching ready, with matching boot/
connection IDs, seq greater than last accepted seq, and current control_epoch.
Gaps are allowed; duplicates/stale input are discarded, not recreated. Advance the
transport sequence watermark even when an otherwise valid input has an old epoch.
Pico does not retry button messages. Suppress gestures until the first valid view,
and require release of already-held buttons after boot/connection reset.

**Pico never sends semantic Feed/End/Pause commands, chosen focus durations, mood
decisions, elapsed time, calculated breaks, or completion events.** Laptop controls
resolve the physical press against the current screen.

## Laptop → Pico: connection messages

```json
{"v":2,"type":"hello","connection_id":"link-001"}
{"v":2,"type":"ping","connection_id":"link-001","nonce":7}
```

A hello clears previous views/cues and resets button sequence, revision and epoch
tracking; Pico replies ready and keeps its connection overlay until the first
valid render. Other messages must match that accepted connection ID.

Baseline heartbeat: laptop pings every 2 seconds, times out after 6 seconds without
matching pong; Pico times out after 6 seconds without valid current-session host
traffic. Timing changes must remain compatible at both ends. Timeout shows
“Connect laptop,” hides the stale countdown and suppresses gestures/animations
until a fresh hello. The laptop's timer keeps running if only USB was disconnected.

## Laptop → Pico: render

Each message carries a complete view. Examples are independent screen fixtures;
navigation does not have to follow their order.

[Canonical render fixtures](../contracts/laptop_to_pico.v2.jsonl) are the executable examples for every screen. Keep that file, both validators and this field table synchronized.

Revisions 3 and 4 are the same focus screen and control_epoch: revision 4 is
what pressing button 1 (Time) produces, showing the real clock instead of the
countdown for five seconds. Revealing the clock is a visible change like any
other clock/timer/mood update, so it still gets a new revision; it does not
bump control_epoch because button meanings have not changed. When the five
seconds elapse, the laptop publishes another new revision restoring
`clock_text: null` and the current `timer_seconds`, still under that same
epoch.

Feed-menu example (labels carry the configured display choice and price while the
laptop remains authoritative for affordability and spending):

```json
{"v":2,"type":"render","connection_id":"link-001","revision":8,"view":{"screen":"feed","control_epoch":8,"mood":"calm","clock_text":null,"timer_seconds":null,"paused":false,"focus_minutes":null,"break_minutes":null,"buttons":[{"button":1,"label":"Jollof 3Y","enabled":true},{"button":2,"label":"Coffee 2Y","enabled":true},{"button":3,"label":"Back","enabled":true}],"feedback":null,"progression":{"level":1,"xp_into_level":0,"xp_for_next_level":75,"yarn_balance":10}}}
```

| Field | Contract |
| --- | --- |
| revision | Positive increasing per connection; ignore duplicate/older snapshots; gaps allowed |
| screen | home, feed, setup, focus, break_offer, break |
| control_epoch | Positive, nondecreasing across accepted snapshots; changes when button meanings change, not each countdown tick |
| mood | idle, happy, sad, hungry, working_neutral, working_sad, sleeping, party; laptop chooses |
| clock_text | Valid 24-hour HH:MM on home, or on focus while the laptop is revealing the real time; null elsewhere |
| timer_seconds | Integer 0–3,600 on focus/break when clock_text is null there; null whenever clock_text is set or outside focus/break; never decrement locally |
| paused | Boolean; false outside focus/break; always false on break, which has no paused state |
| focus_minutes | Integer multiple of 5 from 5–60 on setup; null elsewhere |
| break_minutes | Integer 1–60 on setup/break_offer; null elsewhere |
| buttons | One {button, label, enabled} per advertised ID, in advertised physical order; label is printable ASCII 1–12 characters, enabled is boolean |
| feedback | null, unavailable, or storage_error |
| progression | On Home and Feed: `{level, xp_into_level, xp_for_next_level, yarn_balance}`; null elsewhere. Physical production UI draws only level/yarn; exact XP fields support dev diagnostics. |
| earned_rewards | On break_offer: `{xp, yarn}` for the completion just awarded; null on other screens |

All keys are required, with null for absent content. Reject inconsistent fields
and decreasing epochs. Swapping the validated desired view is atomic in RAM;
physical LCD painting can take multiple slices. Firmware draws the selected screen
layout, small face on timers and large pet at home, without interpreting actions.
It may format seconds as MM:SS; remaining time is always laptop-supplied.

Storage_error displays an overlay hiding a potentially stale countdown. Disabled
buttons are styling; raw gestures may still be reported and the laptop rejects
gameplay while storage is unavailable. There are no care-stat, food-price,
accessory or timer-progress-art fields.

Publish on connection, navigation, accepted actions, and visible clock/timer/mood
changes. While a timer runs, publish when its visible whole-second value changes,
approximately once per second. Coalesce to the newest unsent view. Reset revision/
epoch for a fresh connection; no old view or queued input survives it.

## Laptop → Pico: animate

```json
{"v":2,"type":"animate","connection_id":"link-001","animation_id":"event-uuid:feed","after_revision":8,"name":"feed","food_sprite":"food_basic"}
{"v":2,"type":"animate","connection_id":"link-001","animation_id":"event-uuid:celebrate","after_revision":9,"name":"celebrate","food_sprite":null}
```

Required fields: name is feed or celebrate; food_sprite is food_basic for feed
and null for celebrate. Animation ID is printable ASCII, 1–96 characters, derived
from the committed event ID and cue name. after_revision is a positive revision
already applied, or surpassed, before playing. Drop an early cue; do not wait
blocking for a missing frame. The host sends an adequate snapshot first.

Playback is best effort: keep a bounded queue/recent-ID cache (proposed 32 IDs),
drop stale cues under load, and never resend after restart/reconnect. Navigation
supersedes incompatible animations: feeding belongs on home and celebration on
break_offer. Cues never block button/USB polling or change the timer/screen.

Sprites and animation frames are firmware assets and never travel over this JSON
link. The laptop sends only the agreed mood, sprite/animation identifier and timing
metadata; the Pico selects and draws its locally stored frames.

Changing food appearance is an asset change; adding new asset IDs requires updating
the agreed UI vocabulary. Changing timer, grace or reaction rules needs no firmware
game logic. Coordinate future incompatible wire revisions with both owners.

## Performance evidence

Keep JSON unless measurements on the selected board show it is the bottleneck.
For the largest valid fixture and an ordinary timer render, record line size, JSON
decode/validation time, display update time, free-memory change and button-to-render
round-trip latency. Test repeated timer updates long enough to reveal allocation or
garbage-collection spikes. Identify which stage dominates before shortening fields
or replacing the format. Store the results in the Pico README's table and reference
them when completing M21.

## Progression/economy contract expansion

M24 adds the required nullable `progression` field shown above; the shared fixture
exercises its Home form. M25 must add Feed-menu item names/prices through a
coordinated schema/UI update. Pico receives display-ready values and animation IDs,
but never sensor streams, reward rules or authority to spend yarn. Update fixtures
and both validators together for future incompatible fields.
