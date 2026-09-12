"""Dependency-inversion interfaces for stateful or external resources."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from deskpet.core.events import DomainEvent, UncommittedEvent
from deskpet.core.models import ClockReading, PublishStatus, WeeklyReport
from deskpet.core.views import AnimationCue, InputMessage, RenderSnapshot


@dataclass(frozen=True, slots=True)
class AppendResult:
    inserted: bool
    event: DomainEvent


class Clock(Protocol):
    def read(self) -> ClockReading: ...


class EventStore(Protocol):
    def append(self, event: UncommittedEvent) -> AppendResult: ...

    def read_after(self, seq: int = 0) -> Iterable[DomainEvent]: ...

    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class DeviceSelector:
    port: str | None = None
    vendor_id: int | None = None
    product_id: int | None = None
    serial_number: str | None = None


@dataclass(frozen=True, slots=True)
class SerialCandidate:
    port: str
    vendor_id: int | None
    product_id: int | None
    serial_number: str | None
    description: str | None


class DeviceEnumerator(Protocol):
    def list(self) -> tuple[SerialCandidate, ...]: ...


@dataclass(frozen=True, slots=True)
class DeviceResolved:
    candidate: SerialCandidate


@dataclass(frozen=True, slots=True)
class DeviceNotFound:
    selector: DeviceSelector


@dataclass(frozen=True, slots=True)
class DeviceAmbiguous:
    candidates: tuple[SerialCandidate, ...]


ResolveResult = DeviceResolved | DeviceNotFound | DeviceAmbiguous


class DeviceResolver(Protocol):
    def resolve(
        self,
        selector: DeviceSelector,
        candidates: tuple[SerialCandidate, ...],
    ) -> ResolveResult: ...


InputCallback = Callable[[InputMessage], None]


class DeviceLink(Protocol):
    def start(self, on_input: InputCallback) -> None: ...

    def publish(self, view: RenderSnapshot, revision: int) -> PublishStatus: ...

    def animate(self, cue: AnimationCue) -> PublishStatus: ...

    def stop(self) -> None: ...


class ConfigLoader[ConfigT](Protocol):
    def load(self, path: Path) -> ConfigT: ...


class ReportFormatter(Protocol):
    def format(self, report: WeeklyReport) -> str: ...
