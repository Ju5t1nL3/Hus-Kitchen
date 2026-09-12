# Events, timers and emotions

The laptop stores an append-only SQLite event history. `GameState` is rebuilt from
it; screen selection and live timer clock anchors are separate temporary state.
This is the revised emotion-only schema, version 2. The former stats/shop schema
was a plan, not implemented data; do not accept it silently as the new schema.

## Envelope and storage

| Field | Type / purpose |
| --- | --- |
| `seq` | SQLite-assigned positive integer; replay in this order |
| `event_id` | UUID generated before append |
| `schema_version` | Integer 2 |
| `type` | One of the event types below |
| `occurred_at` | Laptop UTC ISO-8601 timestamp |
| `user_id`, `device_id` | Stable local player and origin installation IDs |
| `source` | `system` or `local_controls`; session lifecycle always uses system |
| `dedupe_key` | Semantic operation identity within user/source scope |
| `payload` | Validated typed event data |

Use a unique event ID and unique `(user_id, source, dedupe_key)`. Append one event
per transaction and return only after commit. A retry returns the existing event
with `inserted=False`; mismatched type/payload is a conflict. Ignore freshly
generated timestamp/ID differences when comparing otherwise identical retries.

The one application writer holds an OS-managed lock for the database path;
read-only report connections are separate. A failed append cannot update gameplay
or trigger an animation. Unknown versions/types or corrupt history stop writable
startup with an actionable error, not a silently reset database.

## Shared records

- `Reaction`: `mood: content|happy|sad`, `expires_at: UTC timestamp`. Resolved
  at the event decision; never extend its expiry during replay.
- `FocusTerms`: selected `duration_seconds`, calculated `break_seconds`,
  `grace_active_ms`, `sad_seconds`, `happy_seconds`, `report_timezone`.
  Pin these at focus start so later config edits cannot change that session.
- `BreakTerms`: `duration_seconds`, `parent_focus_id`, `report_timezone`.
- `BreakOffer`: `parent_focus_id`, `duration_seconds`, `report_timezone`.
  Saved by successful focus completion, consumed by break start or skip.
- `active_ms`: cumulative active time in this session, excluding all pauses.
  Integer milliseconds preserve the exact one-minute boundary.

## Event payloads

| Event | Required payload | Meaning |
| --- | --- | --- |
| `pet_created` | `pet_id` | Initialize identity once; no numerical care stats |
| `pet_fed` | `food_id`, `reaction` (content) | Record free feeding and resolved expression expiry |
| `session_started` | `session_id`, `kind: focus\|break`, kind-specific `terms` | Start running at zero active time; focus updates last confirmed duration; break consumes matching offer |
| `session_paused` | `session_id`, `kind`, `active_ms` | Save cumulative progress and mark paused |
| `session_resumed` | `session_id`, `kind`, `active_ms` | Mark running; active_ms must equal preceding pause |
| `session_completed` | `session_id`, `kind`, `active_ms`, `credit_date`, `break_offer`, `reaction` | Clear session; focus supplies local date, offer and happy reaction; break supplies null for those three fields |
| `session_ended` | `session_id`, `kind`, `active_ms`, `reason`, `reaction` | End without completion; only user_early focus supplies a sad reaction, otherwise null |
| `break_skipped` | `parent_focus_id` | Consume an offered break without a session or mood effect |

End reasons: `user_grace` for focus below its grace threshold; `user_early` for
unfinished focus at/above it; `user_break` for ending a break; or
`app_restart|app_shutdown|suspend|storage_recovery` for neutral interruptions.

Semantic keys:

- Initialization: `pet-created`.
- Feeding: source local_controls, `button:<connection_id>:<button_seq>`.
- Session start: source system, `session-start:<session_id>`.
- Pause/resume: source system, `button:<connection_id>:<button_seq>`.
- End OR completion: source system, `session-terminal:<session_id>`.
- Break start OR skip: source system, `break-choice:<parent_focus_id>`; this
  overrides the ordinary session-start key for a break.

The shared terminal/choice keys prohibit conflicting outcomes. Generate session
IDs and operation keys on the laptop and retain them across an append retry.
A duplicate append never causes another reaction notification or animation.

## Timer calculation and pause/resume

The clock provides UTC and monotonic milliseconds. For a running timer:
`active_ms = min(duration_ms, committed_active_ms + now_mono - run_anchor_mono)`.
For a paused timer: `active_ms = committed_active_ms`.
Remaining display seconds are `ceil((duration_ms - active_ms) / 1000)`.

Start/resume establish a temporary monotonic anchor. Pause samples elapsed active
time and stores it before freezing the UI. Resume stores a resume event before
establishing the next anchor. Neither pauses nor pause durations count as focus.
End while paused uses the saved active time. Do not write events every second.

The scheduler alone can issue completion, and only for a running timer at its
deadline. It processes due completion before buttons: an End/Pause arriving at
the deadline cannot replace a completion. A screen-control token prevents that
old button from then activating a different action on the new break-offer screen.

Detect an OS resume, a large loop gap (proposed over five seconds with normal
one-second wakeups), or a large UTC/monotonic discrepancy before completion.
End any running or paused session neutrally; do not credit the interrupted gap.
Long process stalls or clock adjustments may conservatively trigger the same
policy. Validate this on the selected laptop OS.

On restart there is no trusted running anchor. End the unfinished session using
only its last persisted active_ms; unsaved time since its last start/resume is
unknown and excluded. Manual End/grace classification uses an accurate live
sample; system interruption reasons never produce sadness. Graceful shutdown can
sample active time before its neutral end. Breaks follow the same recovery policy.

## Replay and emotion selection

Replay starts at None, requires one pet_created, and applies events by increasing
seq. Validate session identity/kind and transitions: pause requires running,
resume requires paused, terminal events require that session to exist. Active
time cannot decrease or exceed duration; completion equals duration; user ends
and pause samples must be below duration. Break start/skip requires a matching
pending offer, with duration, parent ID and timezone equal to that saved offer.
Only one session or break offer can exist at a time. Focus start requires neither.

Reducers never read clocks/config or perform I/O. They retain the current session,
last confirmed focus duration, pending break, latest reaction candidate and
qualifying focus dates. A null reaction does not erase a previous candidate.

`emotions.select(state, now_utc)` uses the latest reaction if unexpired, otherwise
focused for running focus, resting for running break, or calm. Paused sessions
default to calm. When a newer reaction expires, do not revive an older one.
This makes the emotion a simple query over recorded facts and current time;
the projection avoids rescanning the entire history on every redraw.

Reaction expiry is calculated when the event is accepted, using pinned session
terms or the current food definition. Old reactions keep their original expiry
after config changes/restarts; restarting never replays their animations.
There is no decay log, offline penalty, emotion score or hidden pet-stat model.

## Streak and weekly text recap

Only completed focus sessions add a qualifying date. Store that completion date
using the timezone pinned at focus start, including when a session spans midnight.
Existing credit dates do not shift when timezone configuration changes.

Current streak counts consecutive dates ending today, or yesterday if today has
not qualified; otherwise zero. Pass today explicitly to the pure query.

Weekly reports cover seven local dates from week_start (normally Monday), with
completed focus count and minutes, early-ended focus count and active minutes,
interrupted focus count and recorded active minutes, break count, feed count, and
current streak. Break count includes both completed and ended break sessions.
Paused and break time never count as focus; incomplete sessions do not count as completed.
Attribute completed focus to credit_date and other events by occurred_at in the
requested report timezone. Count each session only from its terminal event;
never sum cumulative pause/resume samples. Interrupted active time is a lower
bound because unsaved running time can be lost; label it accordingly.

Queries are read-only. A future dashboard or integration reuses them rather than
mutating history. Version future schema changes explicitly; local seq and origin
tags alone are not a co-op synchronization/conflict policy.

The first post-MVP extension is [XP/coins and optional activity bonuses](progression_design.md).
It adds versioned policy/summary data and a deduplicated reward event. Keep the
MVP schema above unchanged until that milestone; keyboard/head adapters do not
write balances directly. Numerical care stats are permanently excluded.
