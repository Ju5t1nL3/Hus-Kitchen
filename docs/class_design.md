# MVP class and function contracts

Status: proposed Python-style signatures, not existing code. Types in this file
are API contracts; serialization is defined in [serial_protocol.md](serial_protocol.md)
and [event_model.md](event_model.md). Use frozen dataclasses/typed unions on the
laptop. Firmware may use validated dictionaries and small classes to suit memory.

## Core records

| Type | Fields / invariants |
| --- | --- |
| `PetStats` | `hunger`, `friendship`, `health: int`, each 0–100; hunger means fullness |
| `FocusSession` | `session_id: str`, `duration_seconds: int`, `reward_coins: int`, `reward_friendship: int`, `report_timezone: str` |
| `GameState` | `user_id: str`, `pet: PetStats`, `coins: int >= 0`, `owned_accessories: frozenset[str]`, `equipped_accessory: str \| None`, `active_session: FocusSession \| None`, `focus_dates: frozenset[date]`, `last_seq: int` |
| `ClockReading` | `utc: aware datetime`, `monotonic_seconds: float`, `resumed: bool`; one clock sample |
| `UiState` | mode, selected menu ID, feedback/expiry, temporary sad expiry, completion-display expiry, runtime deadline, decay remainder; connection status belongs here, not in `GameState` |
| `InputMessage` | Union of validated `DeviceReady`, `ButtonInput`, `Pong`, `ConnectionChanged`, `Tick`, `Shutdown` |
| `ButtonInput` | connection ID, boot ID, sequence, physical button ID, gesture; laptop receive time attached internally |
| `EventDraft` | typed event name/payload, source, dedupe key; no `seq` or timestamp |
| `DomainEvent` | draft fields plus ID, UTC timestamp, user/device IDs, schema version and committed `seq` |
| `Decision` | `event: EventDraft \| None`, `rejection: Rejection \| None`; never both; neither means harmless no-op |
| `Rejection` | code from `insufficient_coins`, `unavailable`, `already_active`, `no_active_session`, `invalid_item`; no exception for ordinary user mistakes |
| `RenderSnapshot` | the complete `view` shape in the serial spec; no event or reward data |
| `AnimationCue` | ID, name, required render revision; transport supplies connection ID |
| `WeeklyReport` | week start, timezone, completion count, focus seconds, earned/spent coins, daily totals, current streak |
| `Rules` | validated pet/focus/shop config records, including explicit prices/effects/thresholds |

Owned accessories are immutable sets; there is no general inventory hierarchy in
MVP. `FocusSession` stores promised terms, not a mutable countdown. Streak is a
query over completion dates, not an independently editable counter.

## Commands and routing

| Command | Input fields | Owner / outcome |
| --- | --- | --- |
| `OpenMenu`, `NextMenuItem`, `BackToClock` | Optional initial selected ID | UI only; no event |
| `StartFocus` | Application-generated `session_id` | Focus feature; start event with configured terms |
| `CancelFocus` | active session ID and reason | Focus feature; neutral cancellation |
| `CompleteFocus` | active session ID | Scheduler only; completion with pinned rewards |
| `FeedPet` | `food_id`, operation key | Pet feature; validated stat effects + payment in one event |
| `PerformTrick` | trick ID, operation key | Pet feature; recorded trick, no repeatable coin reward |
| `ApplyDecay` | accepted awake seconds, operation key | Scheduler only; resolved stat effects |
| `BuyAccessory` | accessory ID, operation key | Shop feature; payment + ownership in one event |
| `EquipAccessory` | owned accessory ID or null, operation key | Shop feature; equipped selection |

`CompleteFocus` and `ApplyDecay` cannot originate from a device or future external
adapter. The application validates internal command provenance and deadline due
status. Public inputs cannot supply their own reward amounts. The fixed dispatch
table selects the appropriate feature; ordinary button input is never broadcast
to every feature to interpret independently.

## Pure game APIs

| Function | Inputs → output | Contract |
| --- | --- | --- |
| `pet.decide(state, command, rules) -> Decision` | Current immutable state, pet command, pet/shop food rules | Feed/trick/decay checks; exact clamped effects; no time reads or I/O |
| `focus.decide(state, command, rules, now) -> Decision` | State, focus command, focus rules, explicit clock reading | Start/cancel/complete transitions; use active session's pinned terms on completion |
| `shop.decide(state, command, rules) -> Decision` | State, shop command, shop rules | Validate item, funds, ownership; no-op/reject repeat purchases/equips |
| `pet.apply(state, event) -> GameState` | Pet-owned committed event | Apply only stored facts; reject malformed transition |
| `focus.apply(state, event) -> GameState` | Focus-owned committed event | Update session, reward and dates atomically |
| `shop.apply(state, event) -> GameState` | Shop-owned committed event | Update coins/ownership/equipped selection |
| `replay.reduce(state, event) -> GameState` | `GameState \| None`, committed event | Dispatch by event type; initialization owns `None` case; update `last_seq` |
| `replay.rebuild(events) -> GameState \| None` | Ordered iterable of committed events | Pure fold; empty log returns None; unknown/invalid history raises `ReplayError` |
| `history.current_streak(dates, today) -> int` | Qualifying dates, explicit local today | Today/yesterday rule in event model; no hidden clock |
| `history.summarize(events, week_start, timezone, today) -> WeeklyReport` | User's history, local date/timezone and today | Query only; history may include earlier dates needed for streak |

`pet_created` initialization is handled by `replay.reduce`; a small pure
`make_initial_event(rules, identity) -> EventDraft` constructs its proposed values.
Rule functions share value records, not mutable service singletons. An event
type has exactly one reducer owner, even if it changes multiple fields.

## Laptop application and presentation

| API | Inputs → output | Side effects / responsibility |
| --- | --- | --- |
| `Application(store, device, clock, config)` | Injected ports/config → coordinator | Holds game/UI state and input queue; constructor does not start workers |
| `Application.start() -> None` | No arguments | Validate/load/replay, neutral restart recovery, start device adapter |
| `Application.run() -> None` | No arguments | Queue loop with deadline timeout until shutdown; only state writer |
| `Application.handle(input, now) -> None` | Typed input + clock sample | Process due work, validate connection, route/commit/reduce/present |
| `Application.stop() -> None` | No arguments | Neutral shutdown cancellation, stop/join workers, close resources; idempotent |
| `controls.resolve(button, ui, state, controls_config) -> UiAction \| CommandIntent \| None` | Raw validated gesture and explicit context | Maps gesture to intention; no I/O, session-ID generation or mutations |
| `controls.apply_ui(ui, action) -> UiState` | UI state + navigation action | Pure selection/mode changes; no game effects |
| `scheduling.advance(ui, state, previous, now, config) -> ScheduleResult` | Time samples and current state | Produces updated timing state and due command intents in defined order; interruption before completion |
| `presenter.build(state, ui, now, config) -> RenderSnapshot` | Game/UI state + explicit time + display rules | Mood precedence, timer text values, stage, menu price/enabled, hidden stats |
| `presenter.on_commit(event, ui, now, config) -> PresentationResult` | Newly committed event only | Updated UI plus cue names; pure; never called by replay |
| `make_envelope(draft, identity, now, event_id) -> UncommittedEvent` | Explicit draft/identity/time/UUID | Validate and stamp envelope; application generates UUID outside pure rules |

`CommandIntent` contains semantic action and relevant item/session identity;
the application supplies operation keys and generated session IDs before dispatch.
`ScheduleResult` contains new temporary timing state and ordered command intents,
not precomputed event effects. Re-evaluate each intent against the latest committed
state, especially after decay changes stats. A rejected due command does not
generate duplicate completion attempts forever; refresh deadlines from current state.

`PresentationResult` updates only ephemeral UI and identifies optional live cues.
On completion, retain a zero-second focus view at progress stage 8 for the
configured brief completion interval (proposed two seconds), then show the clock.
There is already no active durable session during that view. A hold dismisses the
completion view without generating a cancellation; short presses remain ignored.
After restart/reconnect, do not restart expired presentation effects.

Use `ceil(max(0, deadline - now.monotonic_seconds))` for a running countdown and
`min(8, floor(8 * elapsed / duration))` for progress. Both are laptop calculations.
The presenter receives enough explicit state to handle completed-focus display
without inventing a second active session.

## Resource ports and implementations

Declare small structural interfaces (`typing.Protocol`) in `core/ports.py`.

| Port/API | Inputs → output | Contract |
| --- | --- | --- |
| `Clock.read() -> ClockReading` | No input → sample | Implemented by `SystemClock` and `FakeClock`; isolate OS differences |
| `EventStore.append(event) -> AppendResult` | Valid uncommitted event → `inserted: bool`, committed event | Commit before returning; duplicate returns existing event; conflict/storage failure raises typed error |
| `EventStore.read_after(seq=0) -> Iterable[DomainEvent]` | Exclusive sequence cursor → committed ordered rows | Stable ordered read; no rewrite of history |
| `EventStore.close() -> None` | No input | Release connection; idempotent |
| `DeviceLink.start(on_input) -> None` | Thread-safe callback accepting `InputMessage` | Start workers; callback only enqueues, never runs rules |
| `DeviceLink.publish(snapshot, revision) -> PublishStatus` | Complete view + app revision → `queued` or `disconnected` | Nonblocking; newest snapshot supersedes older unsent snapshots |
| `DeviceLink.animate(cue) -> PublishStatus` | Cue → `queued`, `dropped`, or `disconnected` | Bounded, best-effort; no game-state consequence |
| `DeviceLink.stop() -> None` | No input | Stop/join workers, close port; bounded shutdown wait |
| `wire_codec.decode_line(bytes) -> ParseResult` | One bounded line → typed device message or parse diagnostic | Pure parse/shape validation; connection/sequence checks belong to link |
| `wire_codec.encode(message) -> bytes` | Typed outbound message → complete newline-terminated bytes | Pure validation/serialization; raises `EncodeError` if invalid/oversized |
| `config_loader.load(path) -> AppConfig` | YAML path → validated nested config | File I/O; errors identify field and cause; no partially valid config |
| `text_report.format(report) -> str` | `WeeklyReport` → printable text | Pure formatter; CLI owns stdout/file writing |

`SqliteEventStore(path, writable=True)` owns SQL, schema setup and transaction
behavior. Opening writable mode acquires an exclusive application lock associated
with that database path and fails clearly if another game process holds it;
release it on close. Use an OS-managed lock that is released on process death,
not only a stale PID file. Read-only report connections do not need that lock.
One application thread owns the writable connection. `ReportService(store, timezone)` provides
`weekly(week_start, today) -> WeeklyReport` by reading events and calling the pure
history query. A separate report CLI process opens its own read connection; never
share a SQLite connection between arbitrary threads.

`SerialDeviceLink` owns connection IDs, handshake/heartbeat, message validation,
byte buffers and sequence tracking. It emits `ConnectionChanged` before inputs
for a new connection. The application resets its render revision on each new
connection, and re-publishes its current snapshot after matching ready. Serial
workers must not hold a lock while calling into the application queue.

Ordinary invalid actions use `Decision.rejection`; corrupt history, persistence
failure and broken configuration use explicit exceptions with actionable context.
Connection loss is an input/status, not a reason to crash the game. No API returns
an ambiguous boolean where callers need to distinguish duplicate/rejected/failed.

## Firmware classes and functions

| API | Inputs → output | Responsibility |
| --- | --- | --- |
| `ButtonScanner(pins, debounce_ms, hold_ms)` | Hardware inputs/config → scanner | Own per-button raw/stable state and gesture timing |
| `ButtonScanner.poll(now_ms) -> list[ButtonGesture]` | Wrap-safe ticks → zero or more `{button, action}` | Read pins; debounce; one press OR hold per gesture |
| `ButtonScanner.reset_until_release() -> None` | No input | Suppress already-held buttons across connection resets |
| `Protocol.feed(chunk) -> list[HostMessage]` | Available bytes → zero/multiple validated messages | Bounded assembly/parse; incomplete suffix retained |
| `Protocol.accept(message, now_ms) -> DeviceAction \| None` | Parsed message/time → hello/render/animation/ping action | Enforce connection/revision rules; no game decisions |
| `Protocol.encode_ready/button/pong(...) -> bytes` | Fields specified in serial spec → framed bytes | Only outbound protocol messages; no debug printing |
| `Renderer.set_view(view) -> None` | Valid complete snapshot | Replace desired view; mark affected regions dirty |
| `Renderer.enqueue_animation(cue) -> None` | Valid cue | Bounded recent-ID/animation tracking; drop stale cues |
| `Renderer.set_connected(value) -> None` | Boolean link state | Show/hide neutral connection overlay; clear transient cues on disconnect |
| `Renderer.tick(now_ms) -> None` | Current firmware ticks | Advance visual frames and repaint bounded work; no timer/stat calculations |
| `DisplayDriver.draw_region(rect, pixels) -> None` | Display bounds + pixel buffer | Hardware-specific drawing only; implementation may chunk large writes |
| `FirmwareApp.step(now_ms) -> None` | One loop timestamp | Read available USB, dispatch messages, poll buttons, flush bounded output, draw one work slice |

Pin electrical levels never leave `ButtonScanner`; physical gesture IDs do.
Renderer may format seconds as text, choose animation frames, and clip drawing;
it cannot derive mood, progress stage, costs, or menu selection. Keep driver and
sprite asset edits independent from laptop business rules.
