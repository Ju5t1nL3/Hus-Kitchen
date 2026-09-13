# MVP class and function contracts

Proposed laptop interfaces for the current emotion-only MVP. Use immutable typed
records, tagged unions and pure rule functions. Stateful resource classes are
injected. The [event model](event_model.md) owns saved payload semantics; the
[serial protocol](serial_protocol.md) owns wire fields and bounds.

## Core types

Define these in core rather than passing raw dictionaries through laptop modules:

```python
Screen = Literal["home", "feed", "setup", "focus", "break_offer", "break", "settings"]
Mood = Literal["idle", "happy", "sad", "hungry", "working_neutral", "working_sad", "sleeping", "party"]
SessionKind = Literal["focus", "break"]
SessionStatus = Literal["running", "paused"]
Gesture = Literal["press", "hold"]
RejectionCode = Literal["unavailable", "invalid_duration", "invalid_food",
                        "no_session", "wrong_session_state", "no_break_offer"]
PublishStatus = Literal["queued", "dropped", "disconnected"]
Feedback = Literal["unavailable", "storage_error"]
```

| Record | Fields / invariants |
| --- | --- |
| FoodDefinition | id/display_name/sprite_id/consume_animation, positive price_yarn and reaction duration; configured M25 items are Jollof Rice and Coffee |
| Reaction | mood restricted to content/happy/sad, expires_at: UTC datetime |
| FocusTerms / BreakTerms / BreakOffer | Exact fields from the event model; durations in seconds |
| Session | id: str, kind: SessionKind, matching typed terms, status: SessionStatus, committed_active_ms: int |
| ProgressionState | total_xp/yarn_balance: nonnegative ints, derived positive level, positive policy_version/xp_per_level, nonnegative xp_level_increment |
| GameState | Identity/session/reaction/progression/history fields plus durable independent keyboard_tracking_enabled and camera_tracking_enabled preferences (default false) |
| ClockReading | utc: aware datetime, monotonic_ms: int, resumed: bool |
| RuntimeState | screen/timer/connection fields plus runtime-only sad_pet_count, attention_lost, focus_chain_count and last-earned XP/yarn for the Party view |
| TimerSample | session_id: str, active_ms: int, remaining_seconds: int, due: bool; explicit trusted laptop sample |
| KeyboardSummary | keypress_count: nonnegative int, available: bool; unavailable implies zero, and no key identity can enter this contract |
| ButtonInput | connection_id, boot_id, seq, control_epoch, button: ButtonId (positive int advertised by device), action: Gesture; internal received clock sample |
| RenderSnapshot | Complete typed view from wire spec: screen/epoch/mood, optional clock/timer/duration/progression/settings fields, paused, tuple of ButtonLabels, feedback |
| ButtonLabel | button: ButtonId, label: str, enabled: bool |
| ActionDefinition | id: typed ActionId, label: str, intent: ControlIntent, available: pure predicate on GameState |
| ControlBindings | Mapping from (context, ButtonId, Gesture) to ActionId; context distinguishes running/paused screens |
| AnimationCue | animation_id: str, name: feed or celebrate, after_revision: int, food_sprite: str or None |
| WeeklyReport | week_start: date, timezone: str, completed_focus_count/seconds, early_end_count/active_ms, interrupted_count/recorded_active_ms, break_count, feed_count, daily totals, current_streak |

Source of truth for active time is the saved cumulative sample plus the temporary
running anchor. GameState stores neither a constantly mutating countdown nor an
emotion score. Invariants prohibit simultaneous active_session and pending_break.
After history replay, RuntimeState is reconstructed according to recovery policy.

## Typed unions and results

- InputMessage = DeviceReady | ButtonInput | Pong | ConnectionChanged | Tick | Shutdown.
  DeviceReady/Pong carry the wire fields; ConnectionChanged carries connection ID
  and connected flag; Tick carries a ClockReading; Shutdown carries no game data.
- ControlIntent: zero-field variants FeedDefault, OpenSetup, CycleDuration,
  ConfirmFocus, EndCurrent, PauseCurrent, ResumeCurrent, SkipBreak, StartBreak,
  BackHome, ShowTime, RestartFocus. controls selects one; application supplies
  IDs and current values. ShowTime is a temporary render toggle (below); RestartFocus
  is a compound navigation intent the application resolves into two domain commands
  (see "Repeating the last focus duration").
- DomainCommand: FeedPet(food_id, operation_key), StartFocus(session_id, minutes),
  StartBreak(session_id, parent_focus_id), PauseSession(session_id, operation_key),
  ResumeSession(session_id, operation_key), EndSession(session_id, reason),
  CompleteSession(session_id), SkipBreak(parent_focus_id). End input reason is user
  or a defined system interruption; the feature resolves grace/early/break reason.
- EventDraft: tagged union of per-event records. Each variant fixes its event name
  and typed payload; session variants additionally fix focus/break and matching
  terms. Include source and dedupe_key. Do not allow arbitrary name/payload pairs.
- UncommittedEvent adds UUID, version, UTC and origin fields to the draft.
  DomainEvent adds committed seq. Payload fields are defined in the event model.
- Decision = Accepted(event: EventDraft) | Rejected(code: RejectionCode) | NoOp.
- ParseResult = Parsed(message: DeviceMessage) | Invalid(code: str).
- ScheduleResult = Normal(sample: TimerSample or None, next_wake_mono_ms: int)
  | Interrupted(session_id: str or None, reason: Literal["suspend"]).
- PresentationResult = (screen: Screen, cues: tuple[CueRequest, ...]).
  CueRequest contains name and optional food sprite; the application attaches
  event ID and target render revision when publishing.
- AppendResult = (inserted: bool, event: DomainEvent).

These are record definitions to implement, not loosely typed tuple/dict shortcuts.
Where a fixed enum is specified, use that type rather than an unrestricted string.

## Feature functions

| API | Inputs → output | Contract |
| --- | --- | --- |
| feeding.decide(state, command, food_definitions, now_utc) → Decision | State, FeedPet, immutable ID→definition mapping, explicit time | Current M07 free-feed API; M25 replaces it with balance/price validation and an atomic purchase/feed event |
| timers.break_minutes(focus_minutes, policy) → int | Selected duration and validated break policy | Pure proportional calculation; no Pico involvement |
| timers.decide(state, command, sample, rules, now) → Decision | Immutable state, timer command, TimerSample or None, validated rules and clock reading | Validate transition, pin terms on start, classify early end, build one event |
| rewards.decide(state, focus_session_id, focus_minutes, chain_number, policy) → Decision | Completed focus/break offer, prior totals, runtime chain position and versioned integer rates | Return one deduplicated, fully resolved reward event; no I/O or current-clock dependency |
| preferences.decide_toggle(state, selected_row, operation_key, camera_available) → Decision | Current durable consent plus selected settings row | Toggle an available integration or reject; camera remains unavailable through M28 |
| emotions.select(state, now_utc) → Mood | Event-derived state and explicit UTC | Latest unexpired reaction, then activity default; no I/O or event append |
| replay.apply_event(state, event) → GameState | GameState or None, committed event | Pure reducer: return new state, validate transition and advance last_seq; do not mutate input |
| replay.rebuild(events) → GameState or None | Ordered committed history | Repeatedly call apply_event; empty log returns None, invalid/unsupported history raises ReplayError |
| history.current_streak(dates, today) → int | Qualifying dates and explicit today | Consecutive dates ending today or yesterday |
| history.summarize(events, week_start, timezone, today) → WeeklyReport | User's history and explicit reporting dates | Separate completed focus, early/interrupted time, breaks and feeds |

timers.decide requires a matching trusted sample for pause/end/completion and for
resume validation. Start/skip use None. A paused resume sample equals saved active
time. Recovery supplies last persisted active time for a session whose anchor is
unavailable. Completion requires running and due; only the scheduler can request it.
Feeding is allowed only with no active session or pending break; app also restricts
it to Home. Pure functions cannot produce random IDs or inspect clocks implicitly.

The application creates pet_created on an empty log using configured pet identity.
The small replay module owns the fixed event dispatch; split transition handlers by feature
only if its size warrants it. Progression modules are added in the approved M24–M30
stages described in [progression design](progression_design.md); no numerical care
model is planned.

## Application and UI APIs

| API | Inputs → output | Responsibility |
| --- | --- | --- |
| Application(store, device, clock, config) | Injected ports/config → coordinator | Own GameState, RuntimeState, input queue and render revision; no constructor I/O |
| start() → None | No input | Validate/replay, record neutral restart ending if needed, start USB workers |
| run() → None | No input | Queue loop with scheduled timeouts; only game-state writer |
| handle(input, now) → None | Typed input and time | Check interruption/due completion, reject stale controls, decide/save/apply_event/present |
| stop() → None | No input | Neutral end, stop/join workers, close resources; idempotent |
| controls.resolve(button, runtime, state, bindings, actions) → ControlIntent or None | Valid gesture/context, bindings and action definitions | Look up mapping and check availability; no per-button game rules |
| controls.labels(runtime, state, device_buttons, bindings, actions) → tuple[ButtonLabel, ...] | Same context/bindings/definitions plus advertised physical order | Derive matching labels/enabled states for the presenter |
| controls.navigate(runtime, intent, state, config) → RuntimeState | Navigation intent, explicit state/config | Home/setup selection; wrap allowed minutes; no durable mutation |
| scheduling.sample(session, anchor_mono_ms, now_mono_ms) → TimerSample | Session and live clock anchor | Accumulated active time and ceiling remaining seconds; paused sessions need no anchor |
| scheduling.advance(state, runtime, now, config) → ScheduleResult | State/runtime/time | Detect interruption before evaluating deadline; next wake includes second tick/reaction expiry |
| presenter.build(state, runtime, sample, now, config, actions, device_buttons) → RenderSnapshot | Explicit facts, time, configuration and actions | Uses controls.labels, emotion selector and setup break preview |
| presenter.on_commit(event, runtime, food_definitions) → PresentationResult | Newly committed event + current UI + food assets | Feed stays home; focus completion opens offer; break terminal/early focus goes home |

OpenSetup selects last confirmed duration or the configured default. ConfirmFocus
creates a session ID and uses the current selected minutes. CycleDuration changes
only setup state. BackHome from setup creates no event; Home on a break offer must
commit SkipBreak to consume it.

After commit the application updates run_anchor_mono_ms: start/resume establishes
an anchor from the accepted sample time; pause/end/completion clears it. No anchor
changes on failed writes. After pause, saved elapsed time is the next segment's base.

Render control_epoch increments when navigation or pause/resume changes meanings,
including automatic completion. Input epoch is checked after due work, so an old
Pause cannot start a break. Changes only to mood/time/selected minutes need no new
epoch. Increment render revision for every new snapshot.

Application updates previous_clock on every wake, including interruptions, and
re-establishes scheduling from the resulting state. PresentationResult determines
navigation after every event: session_started selects its timer screen, pause/
resume keeps that screen, break_skipped returns Home, and pet_created selects Home.

## Adding or changing buttons

Use one small action-definition dictionary in app/controls.py, plus declarative
bindings under controls in laptop/config.yaml. Contexts are home, feed, setup,
focus_running, focus_paused, break_offer and break_running; there is no
break_paused context because break sessions cannot be paused. ActionId is a
closed literal/enum matching the defined ControlIntents, not an executable
string. The MVP hardware advertises three physical buttons ([1,2,3]); Home and
break_running bind only two of them, so the third renders as a disabled dash on
those two screens. Example binding subset (not a complete configuration):

```yaml
controls:
  bindings:
    home:
      "1.press": open_feed
      "2.press": open_setup
    feed:
      "1.press": buy_jollof
      "2.press": buy_coffee
      "3.press": back_home
    focus_running:
      "1.press": show_time
      "2.press": pause_current
      "3.press": end_current
```

- Remap an existing action: edit its binding; controls.labels derives the new
  label from the same ActionDefinition. No timer, USB or firmware logic edits.
- Change behavior: edit its owning feature/handler. Keep the physical mapping
  stable unless the user-facing action also changes.
- Add an action: add its typed intent, action definition and application handler,
  then bind it. Reuse existing domain commands where possible. Two ActionIds may
  share one ControlIntent when the same underlying command needs a different
  label per screen: break_running's Home button uses ActionId END_BREAK with the
  EndCurrent intent, distinct from focus's END_CURRENT, purely so the label reads
  "Home" instead of "End".
- Add a physical button: add its ID/GPIO/layout slot to hardware_config.py,
  advertise it in ready, and bind an action. Scanner and codecs iterate declared
  IDs; no button-1/button-2/button-3 branches. Extra labels need usable screen space.

One handler dictionary maps intents to command construction/navigation; no dynamic
plugin loader or large nested button switch. Unbound buttons show a disabled dash
and do nothing. Use the press action for the primary label; if only hold is bound,
show a short hold hint from its definition. The third button now provides an
explicit Back action on setup instead of the earlier two-button hold-to-back;
Setup's press bindings are Up, Set and Back.

## The clock reveal (ShowTime)

ShowTime is bound to a button on focus_running and focus_paused. It is a
temporary render toggle, not a durable event: the application sets
`RuntimeState.clock_reveal_until_mono_ms` to five seconds past the accepted
input's monotonic time and does not touch GameState, save an event, or change
control_epoch (button meanings are unchanged). `presenter.build` compares that
deadline against the current clock on every call and swaps `timer_seconds` for
`clock_text` while it is in the future, so no separate revert step, timer, or
scheduler wake beyond the app's normal per-second refresh is required; the next
ordinary tick after the deadline naturally redraws the countdown.

## Repeating the last focus duration (RestartFocus)

RestartFocus is bound to a button on break_offer and break_running (labeled
Again). It produces two domain commands from one button press instead of one:
first SkipBreak (from break_offer) or EndSession with reason user (from a
running break) to close out the break, then StartFocus using
`state.last_focus_minutes` once that first event is applied, skipping Setup
entirely. The application runs decide/save/apply_event for each command in
sequence and presents only once, after the second event; presenter.on_commit
needs no change for this because the two events it processes,
BreakSkipped/BreakSessionEnded then FocusSessionStarted, already navigate to
Home and then Focus in the existing per-event switch. RestartFocus is
unavailable (and the button greyed out) when `last_focus_minutes` is unset,
which cannot happen once a focus session has ever been confirmed.

Validate bindings at startup/handshake: reject unknown actions, duplicate
(context, button, gesture) entries, unadvertised IDs and layouts that do not fit.
Preserve a route out of each screen. Mapping changes require a new control epoch.
Configuration loads at startup; hot reload remains out of scope.

## Resource interfaces

| Port/API | Inputs → output | Contract |
| --- | --- | --- |
| Clock.read() → ClockReading | No arguments | SystemClock or FakeClock supplies UTC/monotonic/resume data |
| EventStore.append(event) → AppendResult | Valid uncommitted event | Transactional durable write; duplicate returns existing event, conflict/failure raises |
| EventStore.read_after(seq=0) → Iterable[DomainEvent] | Exclusive local cursor | Committed events in increasing seq |
| EventStore.close() → None | No arguments | Idempotent release |
| DeviceEnumerator.list() → tuple[SerialCandidate, ...] | No arguments | Portable adapter returns port plus available USB identity metadata; no gameplay imports |
| DeviceResolver.resolve(selector, candidates) → ResolveResult | Optional configured port/USB identity plus candidates | Exact unique match or explicit not-found/ambiguous result; never silently choose the first port |
| DeviceLink.start(on_input) → None | Thread-safe enqueue callback | Start workers; never invoke game rules on the worker |
| DeviceLink.publish(view, revision) → PublishStatus | Complete view and revision | Nonblocking latest-view queue; queued or disconnected |
| DeviceLink.animate(cue) → PublishStatus | Animation request | Bounded best-effort queue; queued/dropped/disconnected |
| DeviceLink.stop() → None | No arguments | Bounded worker shutdown and port close |
| wire_codec.decode_line(bytes) → ParseResult | One bounded line | Pure shape validation; link checks connection/sequence; app rechecks epoch |
| wire_codec.encode(message) → bytes | Typed host message | Validated newline-terminated JSON; EncodeError for invalid/oversized input |
| config_loader.load(path) → AppConfig | YAML path | I/O and field-specific validation errors |
| text_report.format(report) → str | WeeklyReport | Pure text formatting |

Development composition and simulator APIs are specified in
[development_modes.md](development_modes.md). `SimulatorTransport` implements the
same byte-oriented boundary used below the device link; it does not implement a
second semantic application path. `TraceSink` observes encoded/decoded traffic
without changing acceptance results or writing domain events.

SqliteEventStore(path, writable=True) owns schema/SQL and acquires an OS-managed
exclusive writer lock for the database path; another game writer fails clearly.
A report process uses its own read-only connection. ReportService(store, timezone)
offers weekly(week_start, today) → WeeklyReport through the pure history query.

SerialDeviceLink receives a resolved port and serial backend; it owns handshake,
heartbeat and connection IDs but no OS-specific selection logic. It emits connection
changes before new-session inputs; callbacks only enqueue. Reconnect causes the
application to advance the control epoch and publish current state with a render
revision greater than the retained snapshot. Fake ports,
enumerators and backends have the same signatures. Static checking targets laptop
code; runtime validation still guards every external boundary.

## Firmware APIs

| API | Inputs → output | Responsibility |
| --- | --- | --- |
| ButtonScanner(pins, debounce_ms, hold_ms) | GPIO/config → scanner | Per-button debounce and gesture state |
| poll(now_ms, control_epoch) → list[ButtonGesture] | Wrap-safe ticks and displayed epoch | Read pins; latch epoch at stable down; emit button/action/epoch once |
| reset_until_release() → None | No input | Suppress already-held buttons across resets |
| Protocol.feed(chunk) → list[HostMessage] | Available bytes | Bounded nonblocking line assembly and validation |
| Protocol.accept(message, now_ms) → DeviceAction or None | Parsed message/time | Connection/revision/epoch validation; hello/render/animate/ping action |
| Protocol.encode_ready/button/pong(...) → bytes | Exact wire fields | Framed outbound messages, no semantic game commands |
| Renderer.set_view(view) → None | Valid complete view | Atomic desired-view swap and dirty-region marking |
| Renderer.enqueue_animation(cue) → None | Valid cue | Bounded, compatible visual playback only |
| Renderer.set_connected(value) → None | Boolean | Connection overlay and stale-animation clearing |
| Renderer.tick(now_ms) → None | Firmware ticks | Bounded drawing/animation work; no game countdown |
| DisplayDriver.draw_region(rect, pixels) → None | Bounds and pixel buffer | Hardware-specific drawing; chunk if needed |
| FirmwareApp.step(now_ms) → None | Loop time | Poll USB/buttons, flush bounded output, update display |

Firmware uses validated dictionaries/small classes suited to MicroPython. It never
imports laptop records, infers a mood, calculates a break, or changes a session.
