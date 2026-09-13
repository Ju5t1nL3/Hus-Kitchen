"""Deterministic in-memory implementations of core resource ports."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from deskpet.core.events import DomainEvent, UncommittedEvent
from deskpet.core.models import ClockReading, KeyboardSummary, PublishStatus
from deskpet.core.ports import AppendResult, InputCallback
from deskpet.core.views import AnimationCue, InputMessage, RenderSnapshot


class FakeResourceClosedError(RuntimeError):
    """Raised when a closed fake resource is used."""


class FakeEventConflictError(RuntimeError):
    """Raised when one semantic operation key is reused for different data."""


class FakeClock:
    """Clock controlled explicitly by tests; it never reads the host clock."""

    def __init__(self, reading: ClockReading) -> None:
        self._reading = reading

    def read(self) -> ClockReading:
        return self._reading

    def advance(self, milliseconds: int, *, resumed: bool = False) -> ClockReading:
        if milliseconds < 0:
            raise ValueError("milliseconds must be nonnegative")
        self._reading = ClockReading(
            utc=self._reading.utc + timedelta(milliseconds=milliseconds),
            monotonic_ms=self._reading.monotonic_ms + milliseconds,
            resumed=resumed,
        )
        return self._reading

    def set(self, *, utc: datetime, monotonic_ms: int, resumed: bool = False) -> None:
        self._reading = ClockReading(
            utc=utc,
            monotonic_ms=monotonic_ms,
            resumed=resumed,
        )


class FakeKeyboardTracker:
    """Controllable counter with the same active-segment contract as production."""

    def __init__(self, *, available: bool = True) -> None:
        self.available = available
        self.capturing = False
        self.count = 0
        self.stopped = False

    def begin(self, enabled: bool) -> bool:
        self.stopped = False
        self.count = 0
        self.capturing = enabled and self.available
        return not enabled or self.available

    def pause(self) -> None:
        self.capturing = False

    def resume(self) -> None:
        if self.available:
            self.capturing = True

    def add_presses(self, count: int) -> None:
        if count < 0:
            raise ValueError("count must be nonnegative")
        if self.capturing:
            self.count += count

    def finish(self) -> KeyboardSummary:
        self.capturing = False
        return KeyboardSummary(self.count if self.available else 0, self.available)

    def stop(self) -> None:
        self.capturing = False
        self.stopped = True


class FakeEventStore:
    """Append-only store with the production deduplication contract."""

    def __init__(self, events: Iterable[DomainEvent] = ()) -> None:
        self._events = list(events)
        self._closed = False
        self._validate_seed()

    @property
    def events(self) -> tuple[DomainEvent, ...]:
        return tuple(self._events)

    @property
    def closed(self) -> bool:
        return self._closed

    def append(self, event: UncommittedEvent) -> AppendResult:
        self._ensure_open()
        for existing in self._events:
            if _operation_key(existing.event) != _operation_key(event):
                continue
            if _same_semantic_event(existing.event, event):
                return AppendResult(inserted=False, event=existing)
            raise FakeEventConflictError(
                "dedupe key already belongs to a different event"
            )

        committed = DomainEvent(seq=len(self._events) + 1, event=event)
        self._events.append(committed)
        return AppendResult(inserted=True, event=committed)

    def read_after(self, seq: int = 0) -> Iterable[DomainEvent]:
        self._ensure_open()
        if seq < 0:
            raise ValueError("seq must be nonnegative")
        return tuple(event for event in self._events if event.seq > seq)

    def close(self) -> None:
        self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            raise FakeResourceClosedError("event store is closed")

    def _validate_seed(self) -> None:
        for expected_seq, event in enumerate(self._events, start=1):
            if event.seq != expected_seq:
                raise ValueError("seed events must have contiguous sequence numbers")


@dataclass(frozen=True, slots=True)
class PublishedView:
    view: RenderSnapshot
    revision: int


class FakeDeviceLink:
    """Captures output and lets a test synchronously emit typed device input."""

    def __init__(self, *, connected: bool = True) -> None:
        self.connected = connected
        self.started = False
        self.stopped = False
        self.published: list[PublishedView] = []
        self.animations: list[AnimationCue] = []
        self._on_input: InputCallback | None = None

    def start(self, on_input: InputCallback) -> None:
        if self.started and not self.stopped:
            raise RuntimeError("device link is already started")
        self._on_input = on_input
        self.started = True
        self.stopped = False

    def emit(self, message: InputMessage) -> None:
        if self._on_input is None or self.stopped:
            raise RuntimeError("device link is not running")
        self._on_input(message)

    def publish(self, view: RenderSnapshot, revision: int) -> PublishStatus:
        if not self.connected or self.stopped:
            return PublishStatus.DISCONNECTED
        if revision <= 0:
            raise ValueError("revision must be positive")
        self.published.append(PublishedView(view=view, revision=revision))
        return PublishStatus.QUEUED

    def animate(self, cue: AnimationCue) -> PublishStatus:
        if not self.connected or self.stopped:
            return PublishStatus.DISCONNECTED
        self.animations.append(cue)
        return PublishStatus.QUEUED

    def stop(self) -> None:
        self.stopped = True
        self._on_input = None


def _operation_key(event: UncommittedEvent) -> tuple[str, object, str]:
    return (event.user_id, event.draft.source, event.draft.dedupe_key)


def _same_semantic_event(left: UncommittedEvent, right: UncommittedEvent) -> bool:
    return (
        left.schema_version == right.schema_version
        and left.user_id == right.user_id
        and left.device_id == right.device_id
        and left.draft == right.draft
    )
