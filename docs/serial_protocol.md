# Laptop ↔ Pico protocol v2

Proposed JSON Lines contract for the emotion-only, two-button MVP. It replaces
the earlier unimplemented stats/shop v1. Require `v: 2` and UI `emotions_v1`
on both ends; do not mix examples from the former plan.

## Framing and connection

Each UTF-8 JSON object ends with newline. Maximum line size is 2,048 bytes including
newline; accept optional carriage return before it. Assemble available bytes
without blocking buttons. Discard oversized input through the next newline.
Validate types, required fields, enums and ranges; booleans are not integers.

Ignore unknown message types/extra fields; invalid known messages have no effect.
Unsupported version/UI prevents handshake. A render applies only after the whole
view validates. No REPL/debug printing may share the protocol stream.

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
The MVP advertises [1,2]. Adding an ID within these limits uses the same message
shape and needs no protocol version change. Reject input from unadvertised IDs.
Every render must include each advertised ID exactly once, even if unbound (label
"-", enabled false). The firmware hardware table supplies each ID's layout slot;
button count and actions are not inferred from a screen name.

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

```json
{"v":2,"type":"render","connection_id":"link-001","revision":1,"view":{"screen":"home","control_epoch":1,"mood":"calm","clock_text":"14:32","timer_seconds":null,"paused":false,"focus_minutes":null,"break_minutes":null,"buttons":[{"button":1,"label":"Feed","enabled":true},{"button":2,"label":"Focus","enabled":true}],"feedback":null}}
{"v":2,"type":"render","connection_id":"link-001","revision":2,"view":{"screen":"setup","control_epoch":2,"mood":"calm","clock_text":null,"timer_seconds":null,"paused":false,"focus_minutes":25,"break_minutes":5,"buttons":[{"button":1,"label":"Up","enabled":true},{"button":2,"label":"Confirm","enabled":true}],"feedback":null}}
{"v":2,"type":"render","connection_id":"link-001","revision":3,"view":{"screen":"focus","control_epoch":3,"mood":"focused","clock_text":null,"timer_seconds":1499,"paused":false,"focus_minutes":null,"break_minutes":null,"buttons":[{"button":1,"label":"End","enabled":true},{"button":2,"label":"Pause","enabled":true}],"feedback":null}}
{"v":2,"type":"render","connection_id":"link-001","revision":4,"view":{"screen":"focus","control_epoch":4,"mood":"calm","clock_text":null,"timer_seconds":1470,"paused":true,"focus_minutes":null,"break_minutes":null,"buttons":[{"button":1,"label":"End","enabled":true},{"button":2,"label":"Resume","enabled":true}],"feedback":null}}
{"v":2,"type":"render","connection_id":"link-001","revision":5,"view":{"screen":"break_offer","control_epoch":5,"mood":"happy","clock_text":null,"timer_seconds":null,"paused":false,"focus_minutes":null,"break_minutes":5,"buttons":[{"button":1,"label":"Home","enabled":true},{"button":2,"label":"Start break","enabled":true}],"feedback":null}}
{"v":2,"type":"render","connection_id":"link-001","revision":6,"view":{"screen":"break","control_epoch":6,"mood":"resting","clock_text":null,"timer_seconds":300,"paused":false,"focus_minutes":null,"break_minutes":null,"buttons":[{"button":1,"label":"End","enabled":true},{"button":2,"label":"Pause","enabled":true}],"feedback":null}}
{"v":2,"type":"render","connection_id":"link-001","revision":7,"view":{"screen":"home","control_epoch":7,"mood":"sad","clock_text":"14:35","timer_seconds":null,"paused":false,"focus_minutes":null,"break_minutes":null,"buttons":[{"button":1,"label":"Feed","enabled":true},{"button":2,"label":"Focus","enabled":true}],"feedback":null}}
```

| Field | Contract |
| --- | --- |
| revision | Positive increasing per connection; ignore duplicate/older snapshots; gaps allowed |
| screen | home, setup, focus, break_offer, break |
| control_epoch | Positive, nondecreasing across accepted snapshots; changes when button meanings change, not each countdown tick |
| mood | calm, content, happy, sad, focused, resting; laptop chooses |
| clock_text | Valid 24-hour HH:MM on home; null elsewhere |
| timer_seconds | Integer 0–3,600 on focus/break; null elsewhere; never decrement locally |
| paused | Boolean; false outside focus/break |
| focus_minutes | Integer multiple of 5 from 5–60 on setup; null elsewhere |
| break_minutes | Integer 1–60 on setup/break_offer; null elsewhere |
| buttons | One {button, label, enabled} per advertised ID, in advertised physical order; label is printable ASCII 1–12 characters, enabled is boolean |
| feedback | null, unavailable, or storage_error |

All keys are required, with null for absent content. Reject inconsistent fields
and decreasing epochs. Swapping the validated desired view is atomic in RAM;
physical LCD painting can take multiple slices. Firmware draws the selected screen
layout, small face on timers and large pet at home, without interpreting actions.
It may format seconds as MM:SS; remaining time is always laptop-supplied.

Storage_error displays an overlay hiding a potentially stale countdown. Disabled
buttons are styling; raw gestures may still be reported and the laptop rejects
gameplay while storage is unavailable. There are no stat, wallet, food-price,
accessory or progress-stage fields.

Publish on connection, navigation, accepted actions, and visible clock/timer/mood
changes. Coalesce to the newest unsent view. Reset revision/epoch for a fresh
connection; no old view or queued input survives it.

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

Changing food appearance is an asset change; adding new asset IDs requires updating
the agreed UI vocabulary. Changing timer, grace or reaction rules needs no firmware
game logic. Coordinate future incompatible wire revisions with both owners.

## Progression extension after MVP

The current render schema has no XP/coin fields. Add the top strip through a
coordinated UI/schema update when implementing [progression](progression_design.md);
Pico receives XP progress, level and coin display values but never sensor streams
or reward rules. Ordinary button remapping or adding a declared button does not
require this kind of schema change. This v2 spec is still unreleased; all current
fixtures now include explicit button IDs.
