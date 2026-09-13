"""Temporary SQLite event store for development sessions."""

from pathlib import Path
from tempfile import TemporaryDirectory

from deskpet.adapters.sqlite_event_store import SqliteEventStore
from deskpet.core.events import DomainEvent, UncommittedEvent
from deskpet.core.ports import AppendResult


class TemporaryEventStore:
    """Delegate to real SQLite and remove its private directory on close."""

    def __init__(self) -> None:
        self._directory = TemporaryDirectory(prefix="deskpet-dev-")
        self._store = SqliteEventStore(Path(self._directory.name) / "pet.db")
        self._closed = False

    def append(self, event: UncommittedEvent) -> AppendResult:
        return self._store.append(event)

    def read_after(self, seq: int = 0) -> tuple[DomainEvent, ...]:
        return self._store.read_after(seq)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._store.close()
        finally:
            self._directory.cleanup()
