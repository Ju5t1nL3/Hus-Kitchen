# MVP class and function contracts

Proposed laptop interfaces for the current emotion-only MVP. Use immutable typed
records, tagged unions and pure rule functions. Stateful resource classes are
injected. The [event model](event_model.md) owns saved payload semantics; the
[serial protocol](serial_protocol.md) owns wire fields and bounds.

## Core types

Define these in core rather than passing raw dictionaries through laptop modules:

```python
Screen = Literal["home", "setup", "focus", "break_offer", "break"]
Mood = Literal["calm", "content", "happy", "sad", "focused", "resting"]
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
| FoodDefinition | id: str, sprite_id: str, content_seconds: positive int; MVP only basic/food_basic |
| Reaction | mood restricted to content/happy/sad, expires_at: UTC datetime |
| FocusTerms / BreakTerms / BreakOffer | Exact fields from the event model; durations in seconds |
| Session | id: str, kind: SessionKind, matching typed terms, status: SessionStatus, committed_active_ms: int |
| GameState | user_id: str, pet_id: str, active_session: Session or None, pending_break: BreakOffer or None, last_focus_minutes: int or None, latest_reaction: Reaction or None, focus_dates: frozenset[date], last_seq: int |
| ClockReading | utc: aware datetime, monotonic_ms: int, resumed: bool |
| RuntimeState | screen: Screen, selected_focus_minutes: int, run_anchor_mono_ms: int or None, previous_clock: ClockReading or None, control_epoch: int, connection_id/boot_id: str or None |
| TimerSample | session_id: str, active_ms: int, remaining_seconds: int, due: bool; explicit trusted laptop sample |
| ButtonInput | connection_id, boot_id, seq, control_epoch, button: Literal[1,2], action: Gesture; internal received clock sample |
| RenderSnapshot | Complete typed view from wire spec: screen/epoch/mood, optional clock/timer/duration fields, paused, two ButtonLabels, feedback |
| ButtonLabel | label: str, enabled: bool |
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
  BackHome. controls selects one; application supplies IDs and current values.
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
| feeding.decide(state, command, food_definitions, now_utc) → Decision | State, FeedPet, immutable ID→definition mapping, explicit time | Validate food and idle availability; one free feed event with resolved reaction |
| timers.break_minutes(focus_minutes, policy) → int | Selected duration and validated break policy | Pure proportional calculation; no Pico involvement |
| timers.decide(state, command, sample, rules, now) → Decision | Immutable state, timer command, TimerSample or None, validated rules and clock reading | Validate transition, pin terms on start, classify early end, build one event |
| emotions.select(state, now_utc) → Mood | Event-derived state and explicit UTC | Latest unexpired reaction, then activity default; no I/O or event append |
| replay.reduce(state, event) → GameState | GameState or None, committed event | Initialization then validated transition; advance last_seq |
| replay.rebuild(events) → GameState or None | Ordered committed history | Pure fold; empty log returns None, invalid/unsupported history raises ReplayError |
| history.current_streak(dates, today) → int | Qualifying dates and explicit today | Consecutive dates ending today or yesterday |
| history.summarize(events, week_start, timezone, today) → WeeklyReport | User's history and explicit reporting dates | Separate completed focus, early/interrupted time, breaks and feeds |

timers.decide requires a matching trusted sample for pause/end/completion and for
resume validation. Start/skip use None. A paused resume sample equals saved active
time. Recovery supplies last persisted active time for a session whose anchor is
unavailable. Completion requires running and due; only the scheduler can request it.
Feeding is allowed only with no active session or pending break; app also restricts
it to Home. Pure functions cannot produce random IDs or inspect clocks implicitly.

The application creates pet_created on an empty log using configured pet identity.
The small replay module owns the fixed event dispatch; split reducers by feature
only if its size warrants it. No economy/health/inventory services are needed.

## Application and UI APIs

| API | Inputs → output | Responsibility |
| --- | --- | --- |
| Application(store, device, clock, config) | Injected ports/config → coordinator | Own GameState, RuntimeState, input queue and render revision; no constructor I/O |
| start() → None | No input | Validate/replay, record neutral restart ending if needed, start USB workers |
| run() → None | No input | Queue loop with scheduled timeouts; only game-state writer |
| handle(input, now) → None | Typed input and time | Check interruption/due completion, reject stale controls, decide/commit/reduce/present |
| stop() → None | No input | Neutral end, stop/join workers, close resources; idempotent |
| controls.resolve(button, runtime, state) → ControlIntent or None | Valid physical gesture and current context | Fixed two-button mapping from MVP goals; no I/O |
| controls.navigate(runtime, intent, state, config) → RuntimeState | Navigation intent, explicit state/config | Home/setup selection; wrap allowed minutes; no durable mutation |
| scheduling.sample(session, anchor_mono_ms, now_mono_ms) → TimerSample | Session and live clock anchor | Accumulated active time and ceiling remaining seconds; paused sessions need no anchor |
| scheduling.advance(state, runtime, now, config) → ScheduleResult | State/runtime/time | Detect interruption before evaluating deadline; next wake includes second tick/reaction expiry |
| presenter.build(state, runtime, sample, now, config) → RenderSnapshot | Explicit facts, sample, time and display/focus configuration | Calls pure emotion selector; computes setup break preview and supplies labels |
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

## Resource interfaces

| Port/API | Inputs → output | Contract |
| --- | --- | --- |
| Clock.read() → ClockReading | No arguments | SystemClock or FakeClock supplies UTC/monotonic/resume data |
| EventStore.append(event) → AppendResult | Valid uncommitted event | Transactional durable write; duplicate returns existing event, conflict/failure raises |
| EventStore.read_after(seq=0) → Iterable[DomainEvent] | Exclusive local cursor | Committed events in increasing seq |
| EventStore.close() → None | No arguments | Idempotent release |
| DeviceLink.start(on_input) → None | Thread-safe enqueue callback | Start workers; never invoke game rules on the worker |
| DeviceLink.publish(view, revision) → PublishStatus | Complete view and revision | Nonblocking latest-view queue; queued or disconnected |
| DeviceLink.animate(cue) → PublishStatus | Animation request | Bounded best-effort queue; queued/dropped/disconnected |
| DeviceLink.stop() → None | No arguments | Bounded worker shutdown and port close |
| wire_codec.decode_line(bytes) → ParseResult | One bounded line | Pure shape validation; link checks connection/sequence; app rechecks epoch |
| wire_codec.encode(message) → bytes | Typed host message | Validated newline-terminated JSON; EncodeError for invalid/oversized input |
| config_loader.load(path) → AppConfig | YAML path | I/O and field-specific validation errors |
| text_report.format(report) → str | WeeklyReport | Pure text formatting |

SqliteEventStore(path, writable=True) owns schema/SQL and acquires an OS-managed
exclusive writer lock for the database path; another game writer fails clearly.
A report process uses its own read-only connection. ReportService(store, timezone)
offers weekly(week_start, today) → WeeklyReport through the pure history query.

SerialDeviceLink owns handshake, heartbeat and connection IDs. It emits connection
changes before new-session inputs; callbacks only enqueue. Reconnect causes the
application to reset render revision/epoch and publish current state. Fake ports
have the same signatures. Static checking targets laptop code; runtime validation
still guards every external boundary.

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
