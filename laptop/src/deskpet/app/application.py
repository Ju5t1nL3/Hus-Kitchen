"""Single-writer application coordinator for controls, events and presentation."""

import queue
from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta
from typing import assert_never
from uuid import UUID, uuid4

from deskpet.app import controls, presenter, scheduling
from deskpet.core.commands import (
    Accepted,
    BackHome,
    BuyItem,
    CompleteSession,
    ConfirmFocus,
    ControlIntent,
    CycleDuration,
    Decision,
    EndCurrent,
    EndSession,
    FeedPet,
    NoOp,
    OpenFeed,
    OpenSetup,
    PauseCurrent,
    PauseSession,
    PetOnce,
    Rejected,
    RequestedEndReason,
    RestartFocus,
    ResumeCurrent,
    ResumeSession,
    ShowTime,
    SkipBreak,
    SkipBreakIntent,
    StartBreak,
    StartBreakIntent,
    StartFocus,
)
from deskpet.core.config import AppConfig
from deskpet.core.events import (
    BreakSessionCompleted,
    BreakSessionEnded,
    BreakSessionStarted,
    EventDraft,
    EventSource,
    FocusSessionCompleted,
    FocusSessionEnded,
    FocusSessionPaused,
    FocusSessionResumed,
    FocusSessionStarted,
    PetComforted,
    PetCreated,
    ProgressionInitialized,
    UncommittedEvent,
)
from deskpet.core.models import (
    ButtonId,
    ClockReading,
    Feedback,
    GameState,
    Reaction,
    ReactionMood,
    RejectionCode,
    RuntimeState,
    Screen,
    SessionKind,
    TimerSample,
)
from deskpet.core.ports import (
    AppendResult,
    Clock,
    DeviceLink,
    EventStore,
    EventStoreError,
)
from deskpet.core.views import (
    AnimationCue,
    ButtonInput,
    ConnectionChanged,
    CueRequest,
    DeviceReady,
    InputMessage,
    InterruptedSchedule,
    NormalSchedule,
    Pong,
    Shutdown,
    Tick,
)
from deskpet.features import feeding, replay, timers

UuidFactory = Callable[[], UUID]


class Application:
    """Coordinate one authoritative state reference and injected resources."""

    def __init__(
        self,
        store: EventStore,
        device: DeviceLink,
        clock: Clock,
        config: AppConfig,
        *,
        uuid_factory: UuidFactory = uuid4,
    ) -> None:
        self._store = store
        self._device = device
        self._clock = clock
        self._config = config
        self._uuid_factory = uuid_factory
        self._inputs: queue.Queue[InputMessage] = queue.Queue()
        self._state: GameState | None = None
        self._runtime: RuntimeState | None = None
        self._device_buttons: tuple[ButtonId, ...] = ()
        self._revision = 0
        self._started = False
        self._stopped = False

    @property
    def state(self) -> GameState:
        return self._require_state()

    @property
    def runtime(self) -> RuntimeState:
        return self._require_runtime()

    def start(self) -> None:
        """Replay durable state, initialize runtime state and start device input."""
        if self._started and not self._stopped:
            raise RuntimeError("application is already started")
        if self._stopped:
            raise RuntimeError("a stopped application cannot be restarted")

        now = self._clock.read()
        state = replay.rebuild(self._store.read_after())
        if state is None:
            created = PetCreated(
                source=EventSource.SYSTEM,
                dedupe_key="pet-created",
                pet_id=self._config.identity.pet_id,
            )
            state = replay.apply_event(None, self._append(created, now).event)
        self._state = state
        self._runtime = RuntimeState(
            screen=_startup_screen(state),
            selected_focus_minutes=(
                state.last_focus_minutes or self._config.focus.default_minutes
            ),
            run_anchor_mono_ms=None,
            previous_clock=now,
            control_epoch=1,
            connection_id=None,
            boot_id=None,
        )
        if state.progression is None:
            policy = self._config.progression
            initialized = ProgressionInitialized(
                source=EventSource.SYSTEM,
                dedupe_key="progression-initialized",
                policy_version=policy.policy_version,
                starting_yarn=policy.starting_yarn,
                xp_per_level=policy.xp_per_level,
            )
            self._state = replay.apply_event(
                state, self._append(initialized, now).event
            )
            state = self._state
        if state.active_session is not None:
            self._end_replayed_session(now, RequestedEndReason.APP_RESTART)
        self._started = True
        self._device.start(self._enqueue)

    def run(self) -> None:
        """Process device input and scheduled wakes until shutdown."""
        if not self._started:
            self.start()
        while not self._stopped:
            now = self._clock.read()
            if now.resumed:
                self.handle(Tick(now), now)
                continue
            timeout = self._wait_seconds(now)
            try:
                incoming = self._inputs.get(timeout=timeout)
            except queue.Empty:
                handled_at = self._clock.read()
                incoming = Tick(handled_at)
            else:
                handled_at = self._clock.read()
            self.handle(incoming, handled_at)

    def handle(self, incoming: InputMessage, now: ClockReading) -> None:
        """Handle one typed input after interruption/deadline priority checks."""
        if not self._started or self._stopped:
            raise RuntimeError("application is not running")

        if isinstance(incoming, Shutdown):
            self.stop()
            return
        if isinstance(incoming, ConnectionChanged):
            self._handle_connection(incoming)
            self._set_previous_clock(now)
            return
        if isinstance(incoming, DeviceReady):
            self._handle_ready(incoming, now)
            self._set_previous_clock(now)
            return
        if isinstance(incoming, Pong):
            self._set_previous_clock(now)
            return

        if self.runtime.feedback is Feedback.STORAGE_ERROR:
            self._recover_storage(now)
            self._set_previous_clock(now)
            return

        completed = self._advance_due(now)
        if isinstance(incoming, Tick):
            self._set_previous_clock(now)
            if not completed:
                self._render(now)
            return
        self._handle_button(incoming, now)
        self._set_previous_clock(now)

    def stop(self) -> None:
        """Neutrally end a session, then stop workers and resources idempotently."""
        if self._stopped:
            return
        try:
            if self._started and self._state is not None and self._state.active_session:
                now = self._clock.read()
                session = self._state.active_session
                sample = self._current_sample(now)
                command = (
                    CompleteSession(session.id)
                    if sample is not None and sample.due
                    else EndSession(session.id, RequestedEndReason.APP_SHUTDOWN)
                )
                decision = timers.decide(
                    self._state,
                    command,
                    sample,
                    self._timer_rules(),
                    now,
                )
                self._commit(decision, now, render=False)
        finally:
            self._stopped = True
            try:
                self._device.stop()
            finally:
                self._store.close()

    def _enqueue(self, incoming: InputMessage) -> None:
        self._inputs.put_nowait(incoming)

    def _handle_connection(self, incoming: ConnectionChanged) -> None:
        runtime = self._require_runtime()
        if incoming.connected:
            self._device_buttons = ()
            self._runtime = replace(
                runtime,
                connection_id=incoming.connection_id,
                boot_id=None,
                control_epoch=runtime.control_epoch + 1,
            )
        elif runtime.connection_id == incoming.connection_id:
            self._runtime = replace(runtime, connection_id=None, boot_id=None)
            self._device_buttons = ()

    def _handle_ready(self, incoming: DeviceReady, now: ClockReading) -> None:
        runtime = self._require_runtime()
        if incoming.connection_id != runtime.connection_id:
            return
        controls.validate_bindings(
            self._config.bindings, incoming.buttons, self._config.ui.max_buttons
        )
        self._device_buttons = incoming.buttons
        self._runtime = replace(runtime, boot_id=incoming.boot_id)
        self._render(now)

    def _handle_button(self, incoming: ButtonInput, now: ClockReading) -> None:
        runtime = self._require_runtime()
        if (
            incoming.connection_id != runtime.connection_id
            or incoming.boot_id != runtime.boot_id
        ):
            return
        intent = controls.resolve(
            incoming,
            runtime,
            self._require_state(),
            self._config.bindings,
        )
        if intent is None:
            return

        match intent:
            case OpenFeed():
                if self.state.needs_comfort:
                    return
                self._runtime = controls.navigate(
                    runtime, intent, self.state, self._config.focus, now
                )
                self._render(now)
            case OpenSetup() | CycleDuration() | BackHome() | ShowTime():
                self._runtime = controls.navigate(
                    runtime, intent, self._require_state(), self._config.focus, now
                )
                self._render(now)
            case RestartFocus():
                self._restart_focus(incoming, now)
            case PetOnce():
                self._pet_once(incoming, now)
            case _:
                decision = self._decide(intent, incoming, now)
                self._commit(decision, now)

    def _decide(
        self,
        intent: ControlIntent,
        button: ButtonInput,
        now: ClockReading,
    ) -> Decision:
        state = self._require_state()
        session = state.active_session
        sample = self._current_sample(now)
        operation_key = f"button:{button.connection_id}:{button.seq}"
        match intent:
            case BuyItem(item_id):
                return feeding.decide(
                    state,
                    FeedPet(item_id, operation_key),
                    self._config.feeding.definitions,
                    now.utc,
                )
            case ConfirmFocus():
                return timers.decide(
                    state,
                    StartFocus(
                        str(self._uuid_factory()), self.runtime.selected_focus_minutes
                    ),
                    None,
                    self._timer_rules(),
                    now,
                )
            case EndCurrent():
                if session is None:
                    return Rejected(RejectionCode.UNAVAILABLE)
                return timers.decide(
                    state,
                    EndSession(session.id, RequestedEndReason.USER),
                    sample,
                    self._timer_rules(),
                    now,
                )
            case PauseCurrent():
                if session is None:
                    return Rejected(RejectionCode.UNAVAILABLE)
                return timers.decide(
                    state,
                    PauseSession(session.id, operation_key),
                    sample,
                    self._timer_rules(),
                    now,
                )
            case ResumeCurrent():
                if session is None:
                    return Rejected(RejectionCode.UNAVAILABLE)
                return timers.decide(
                    state,
                    ResumeSession(session.id, operation_key),
                    sample,
                    self._timer_rules(),
                    now,
                )
            case StartBreakIntent():
                offer = state.pending_break
                if offer is None:
                    return Rejected(RejectionCode.UNAVAILABLE)
                return timers.decide(
                    state,
                    StartBreak(str(self._uuid_factory()), offer.parent_focus_id),
                    None,
                    self._timer_rules(),
                    now,
                )
            case SkipBreakIntent():
                offer = state.pending_break
                if offer is None:
                    return Rejected(RejectionCode.UNAVAILABLE)
                return timers.decide(
                    state,
                    SkipBreak(offer.parent_focus_id),
                    None,
                    self._timer_rules(),
                    now,
                )
            case (
                OpenFeed()
                | OpenSetup()
                | CycleDuration()
                | BackHome()
                | ShowTime()
                | RestartFocus()
                | PetOnce()
            ):
                raise ValueError("navigation intent cannot become a domain command")
            case _ as unreachable:
                assert_never(unreachable)

    def _pet_once(self, button: ButtonInput, now: ClockReading) -> None:
        if not self.state.needs_comfort:
            return
        count = self.runtime.sad_pet_count + 1
        if count < 5:
            self._runtime = replace(self.runtime, sad_pet_count=count)
            self._render(now)
            return
        decision = Accepted(
            PetComforted(
                source=EventSource.LOCAL_CONTROLS,
                dedupe_key=f"button:{button.connection_id}:{button.seq}",
                reaction=Reaction(
                    ReactionMood.HAPPY,
                    now.utc + timedelta(seconds=self._config.focus.happy_seconds),
                ),
            )
        )
        if self._commit(decision, now):
            self._runtime = replace(self.runtime, sad_pet_count=0)

    def _restart_focus(self, button: ButtonInput, now: ClockReading) -> None:
        state = self._require_state()
        minutes = state.last_focus_minutes
        if minutes is None:
            return
        if state.pending_break is not None:
            first = timers.decide(
                state,
                SkipBreak(state.pending_break.parent_focus_id),
                None,
                self._timer_rules(),
                now,
            )
        elif (
            state.active_session is not None
            and state.active_session.kind is SessionKind.BREAK
        ):
            first = timers.decide(
                state,
                EndSession(state.active_session.id, RequestedEndReason.USER),
                self._current_sample(now),
                self._timer_rules(),
                now,
            )
        else:
            return
        if not self._commit(first, now, render=False):
            return
        second = timers.decide(
            self._require_state(),
            StartFocus(str(self._uuid_factory()), minutes),
            None,
            self._timer_rules(),
            now,
        )
        self._commit(second, now)

    def _advance_due(self, now: ClockReading) -> bool:
        scheduled = scheduling.advance(self.state, self.runtime, now)
        if isinstance(scheduled, InterruptedSchedule):
            session = self.state.active_session
            if session is None:
                return False
            saved_sample = scheduling.sample(session, None, now.monotonic_ms)
            decision = timers.decide(
                self.state,
                EndSession(session.id, RequestedEndReason.SUSPEND),
                saved_sample,
                self._timer_rules(),
                now,
            )
            return self._commit(decision, now)
        sample = scheduled.sample
        session = self.state.active_session
        if sample is not None and sample.due and session is not None:
            decision = timers.decide(
                self.state,
                CompleteSession(session.id),
                sample,
                self._timer_rules(),
                now,
            )
            self._commit(decision, now)
            return True
        return False

    def _commit(
        self, decision: Decision, now: ClockReading, *, render: bool = True
    ) -> bool:
        if isinstance(decision, Rejected | NoOp):
            return False
        try:
            result = self._append(decision.event, now)
        except EventStoreError:
            self._freeze_for_storage_error(now)
            return False
        current = self._require_state()
        if result.event.seq <= current.last_seq:
            return False
        updated = replay.apply_event(current, result.event)
        presentation = presenter.on_commit(
            result.event, self.runtime, self._config.feeding.definitions
        )
        self._state = updated
        self._update_runtime_after_event(
            result.event.event.draft, presentation.screen, now
        )
        if render:
            self._render(
                now,
                presentation.cues if result.inserted else (),
                result.event.event.event_id,
            )
        return True

    def _end_replayed_session(
        self, now: ClockReading, reason: RequestedEndReason
    ) -> None:
        """End replayed work from its persisted lower bound without side effects."""
        session = self._require_state().active_session
        if session is None:
            return
        decision = timers.decide(
            self.state,
            EndSession(session.id, reason),
            scheduling.sample(session, None, now.monotonic_ms),
            self._timer_rules(),
            now,
        )
        if not self._commit(decision, now, render=False):
            raise EventStoreError("could not persist neutral session recovery")

    def _freeze_for_storage_error(self, now: ClockReading) -> None:
        """Keep the last applied state and stop trusting unsaved timer progress."""
        self._runtime = replace(
            self.runtime,
            run_anchor_mono_ms=None,
            previous_clock=now,
            clock_reveal_until_mono_ms=None,
            feedback=Feedback.STORAGE_ERROR,
            control_epoch=self.runtime.control_epoch + 1,
        )
        self._render(now)

    def _recover_storage(self, now: ClockReading) -> None:
        """Replay authoritative storage before unfreezing gameplay."""
        try:
            rebuilt = replay.rebuild(self._store.read_after())
            if rebuilt is None:
                raise EventStoreError("event history disappeared during recovery")
            self._state = rebuilt
            self._runtime = replace(
                self.runtime,
                screen=_startup_screen(rebuilt),
                run_anchor_mono_ms=None,
                feedback=None,
                control_epoch=self.runtime.control_epoch + 1,
            )
            if rebuilt.active_session is not None:
                self._end_replayed_session(now, RequestedEndReason.STORAGE_RECOVERY)
        except EventStoreError:
            self._freeze_for_storage_error(now)
            return
        self._render(now)

    def _append(self, draft: EventDraft, now: ClockReading) -> AppendResult:
        return self._store.append(
            UncommittedEvent(
                event_id=self._uuid_factory(),
                occurred_at=now.utc,
                user_id=self._config.identity.user_id,
                device_id=self._config.identity.device_id,
                draft=draft,
            )
        )

    def _update_runtime_after_event(
        self, draft: EventDraft, screen: Screen, now: ClockReading
    ) -> None:
        runtime = self.runtime
        anchor = runtime.run_anchor_mono_ms
        meaning_changed = screen is not runtime.screen
        if isinstance(
            draft, FocusSessionStarted | BreakSessionStarted | FocusSessionResumed
        ):
            anchor = now.monotonic_ms
        elif isinstance(
            draft,
            FocusSessionPaused
            | FocusSessionEnded
            | FocusSessionCompleted
            | BreakSessionEnded
            | BreakSessionCompleted,
        ):
            anchor = None
        if isinstance(draft, FocusSessionPaused | FocusSessionResumed):
            meaning_changed = True
        self._runtime = replace(
            runtime,
            screen=screen,
            run_anchor_mono_ms=anchor,
            control_epoch=runtime.control_epoch + int(meaning_changed),
            clock_reveal_until_mono_ms=None,
        )

    def _render(
        self,
        now: ClockReading,
        cues: tuple[CueRequest, ...] = (),
        cue_event_id: UUID | None = None,
    ) -> None:
        if not self._device_buttons:
            return
        scheduled = scheduling.advance(self.state, self.runtime, now)
        sample = scheduled.sample if isinstance(scheduled, NormalSchedule) else None
        snapshot = presenter.build(
            self.state,
            self.runtime,
            sample,
            now,
            presenter.PresenterConfig(
                clock_timezone=self._config.ui.clock_timezone,
                break_policy=timers.BreakPolicy(
                    self._config.focus.focus_minutes_per_break_minute,
                    self._config.focus.minimum_break_minutes,
                ),
                food_definitions=self._config.feeding.definitions,
                hunger_seconds=self._config.feeding.hunger_seconds,
            ),
            self._config.bindings,
            controls.ACTIONS,
            self._device_buttons,
        )
        self._revision += 1
        self._device.publish(snapshot, self._revision)
        for cue in cues:
            if cue_event_id is None:
                raise ValueError("animation cues require a committed event ID")
            self._device.animate(
                AnimationCue(
                    animation_id=f"{cue_event_id}:{cue.name.value}",
                    name=cue.name,
                    after_revision=self._revision,
                    food_sprite=cue.food_sprite,
                )
            )

    def _current_sample(self, now: ClockReading) -> TimerSample | None:
        session = self.state.active_session
        if session is None:
            return None
        return scheduling.sample(
            session, self.runtime.run_anchor_mono_ms, now.monotonic_ms
        )

    def _timer_rules(self) -> timers.TimerRules:
        focus = self._config.focus
        return timers.TimerRules(
            allowed_focus_minutes=focus.allowed_minutes,
            break_policy=timers.BreakPolicy(
                focus.focus_minutes_per_break_minute, focus.minimum_break_minutes
            ),
            grace_active_ms=focus.grace_active_seconds * 1_000,
            sad_seconds=focus.sad_seconds,
            happy_seconds=focus.happy_seconds,
            report_timezone=focus.report_timezone,
        )

    def _wait_seconds(self, now: ClockReading) -> float:
        scheduled = scheduling.advance(self.state, self.runtime, now)
        if isinstance(scheduled, InterruptedSchedule):
            return 0.0
        return max(0.0, (scheduled.next_wake_mono_ms - now.monotonic_ms) / 1_000)

    def _set_previous_clock(self, now: ClockReading) -> None:
        self._runtime = replace(self.runtime, previous_clock=now)

    def _require_state(self) -> GameState:
        if self._state is None:
            raise RuntimeError("application has not started")
        return self._state

    def _require_runtime(self) -> RuntimeState:
        if self._runtime is None:
            raise RuntimeError("application has not started")
        return self._runtime


def _startup_screen(state: GameState) -> Screen:
    if state.pending_break is not None:
        return Screen.BREAK_OFFER
    if state.active_session is not None:
        return (
            Screen.FOCUS
            if state.active_session.kind is SessionKind.FOCUS
            else Screen.BREAK
        )
    return Screen.HOME
