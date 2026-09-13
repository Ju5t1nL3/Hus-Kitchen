"""Durability, idempotency, locking and corruption tests for SQLite events."""

import sqlite3
import tempfile
import unittest
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TypedDict
from uuid import UUID

from deskpet.adapters.sqlite_event_store import (
    ClosedEventStoreError,
    CorruptEventStoreError,
    EventConflictError,
    SqliteEventStore,
    StorageError,
    WriterLockError,
)
from deskpet.core.events import (
    BreakSessionCompleted,
    BreakSessionEnded,
    BreakSessionStarted,
    BreakSkipped,
    EndReason,
    EventDraft,
    EventSource,
    FocusSessionCompleted,
    FocusSessionEnded,
    FocusSessionPaused,
    FocusSessionResumed,
    FocusSessionStarted,
    PetCreated,
    PetFed,
    ProgressionInitialized,
    UncommittedEvent,
)
from deskpet.core.models import (
    BreakOffer,
    BreakTerms,
    FocusTerms,
    Reaction,
    ReactionMood,
)
from deskpet.core.ports import EventStore

NOW = datetime(2026, 9, 13, 4, 30, tzinfo=UTC)
FOCUS_TERMS = FocusTerms(300, 60, 60_000, 30, 30, "America/Chicago")


class DraftMetadata(TypedDict):
    source: EventSource
    dedupe_key: str


def uncommitted(
    number: int,
    draft: EventDraft,
    *,
    occurred_at: datetime | None = None,
) -> UncommittedEvent:
    return UncommittedEvent(
        event_id=UUID(int=number),
        occurred_at=occurred_at or NOW + timedelta(seconds=number),
        user_id="user-1",
        device_id="device-1",
        draft=draft,
    )


def metadata(key: str) -> DraftMetadata:
    return {"source": EventSource.SYSTEM, "dedupe_key": key}


def every_draft() -> tuple[EventDraft, ...]:
    happy = Reaction(ReactionMood.HAPPY, NOW + timedelta(seconds=30))
    sad = Reaction(ReactionMood.SAD, NOW + timedelta(seconds=30))
    content = Reaction(ReactionMood.CONTENT, NOW + timedelta(seconds=20))
    return (
        PetCreated(**metadata("pet-created"), pet_id="pet-1"),
        ProgressionInitialized(
            **metadata("progression-initialized"),
            policy_version=1,
            starting_yarn=10,
            xp_per_level=100,
        ),
        PetFed(
            source=EventSource.LOCAL_CONTROLS,
            dedupe_key="button:c:1",
            food_id="basic",
            reaction=content,
        ),
        FocusSessionStarted(
            **metadata("session-start:focus-1"),
            session_id="focus-1",
            terms=FOCUS_TERMS,
        ),
        BreakSessionStarted(
            **metadata("break-choice:focus-parent"),
            session_id="break-1",
            terms=BreakTerms(60, "focus-parent", "America/Chicago"),
        ),
        FocusSessionPaused(
            **metadata("button:c:2"), session_id="focus-1", active_ms=10_000
        ),
        FocusSessionResumed(
            **metadata("button:c:4"), session_id="focus-1", active_ms=10_000
        ),
        FocusSessionCompleted(
            **metadata("session-terminal:focus-complete"),
            session_id="focus-complete",
            active_ms=300_000,
            credit_date=date(2026, 9, 12),
            break_offer=BreakOffer("focus-complete", 60, "America/Chicago"),
            reaction=happy,
        ),
        BreakSessionCompleted(
            **metadata("session-terminal:break-complete"),
            session_id="break-complete",
            active_ms=60_000,
        ),
        FocusSessionEnded(
            **metadata("session-terminal:focus-ended"),
            session_id="focus-ended",
            active_ms=60_000,
            reason=EndReason.USER_EARLY,
            reaction=sad,
        ),
        BreakSessionEnded(
            **metadata("session-terminal:break-ended"),
            session_id="break-ended",
            active_ms=10_000,
            reason=EndReason.USER_BREAK,
        ),
        BreakSkipped(
            **metadata("break-choice:focus-skip"), parent_focus_id="focus-skip"
        ),
    )


class SqliteEventStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "pet.db"

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_every_event_variant_survives_close_and_reopen(self) -> None:
        events = tuple(
            uncommitted(index, draft)
            for index, draft in enumerate(every_draft(), start=1)
        )
        with SqliteEventStore(self.path) as store:
            port: EventStore = store
            committed = tuple(port.append(event).event for event in events)

        with SqliteEventStore(self.path) as reopened:
            restored = reopened.read_after()

        self.assertEqual(restored, committed)
        self.assertEqual([event.seq for event in restored], list(range(1, 13)))

    def test_semantic_retry_ignores_new_id_and_timestamp(self) -> None:
        draft = every_draft()[0]
        first = uncommitted(1, draft)
        retry = uncommitted(99, draft, occurred_at=NOW + timedelta(days=1))
        with SqliteEventStore(self.path) as store:
            inserted = store.append(first)
            duplicate = store.append(retry)

        self.assertTrue(inserted.inserted)
        self.assertFalse(duplicate.inserted)
        self.assertEqual(duplicate.event, inserted.event)

    def test_terminal_and_break_choice_conflicts_are_rejected(self) -> None:
        ended = FocusSessionEnded(
            **metadata("session-terminal:focus-1"),
            session_id="focus-1",
            active_ms=60_000,
            reason=EndReason.USER_EARLY,
            reaction=Reaction(ReactionMood.SAD, NOW + timedelta(seconds=30)),
        )
        completed = FocusSessionCompleted(
            **metadata("session-terminal:focus-1"),
            session_id="focus-1",
            active_ms=300_000,
            credit_date=date(2026, 9, 12),
            break_offer=BreakOffer("focus-1", 60, "America/Chicago"),
            reaction=Reaction(ReactionMood.HAPPY, NOW + timedelta(seconds=30)),
        )
        started = BreakSessionStarted(
            **metadata("break-choice:focus-2"),
            session_id="break-2",
            terms=BreakTerms(60, "focus-2", "America/Chicago"),
        )
        skipped = BreakSkipped(
            **metadata("break-choice:focus-2"), parent_focus_id="focus-2"
        )

        with SqliteEventStore(self.path) as store:
            store.append(uncommitted(1, ended))
            with self.assertRaises(EventConflictError):
                store.append(uncommitted(2, completed))
            store.append(uncommitted(3, started))
            with self.assertRaises(EventConflictError):
                store.append(uncommitted(4, skipped))

    def test_same_event_id_with_different_operation_conflicts(self) -> None:
        with SqliteEventStore(self.path) as store:
            store.append(uncommitted(1, every_draft()[0]))
            different = UncommittedEvent(
                event_id=UUID(int=1),
                occurred_at=NOW,
                user_id="user-1",
                device_id="device-1",
                draft=PetCreated(
                    source=EventSource.SYSTEM,
                    dedupe_key="another-key",
                    pet_id="another-pet",
                ),
            )
            with self.assertRaises(EventConflictError):
                store.append(different)

    def test_only_one_writer_can_own_a_path(self) -> None:
        first = SqliteEventStore(self.path)
        try:
            with self.assertRaises(WriterLockError):
                SqliteEventStore(self.path)
        finally:
            first.close()

        replacement = SqliteEventStore(self.path)
        replacement.close()

    def test_read_only_store_can_read_while_writer_is_open(self) -> None:
        with SqliteEventStore(self.path) as writer:
            expected = writer.append(uncommitted(1, every_draft()[0])).event
            with SqliteEventStore(self.path, writable=False) as reader:
                self.assertEqual(reader.read_after(), (expected,))
                with self.assertRaisesRegex(StorageError, "read-only"):
                    reader.append(uncommitted(2, every_draft()[1]))

    def test_cursor_and_close_contract(self) -> None:
        store = SqliteEventStore(self.path)
        first = store.append(uncommitted(1, every_draft()[0])).event
        second = store.append(uncommitted(2, every_draft()[1])).event

        self.assertEqual(store.read_after(first.seq), (second,))
        store.close()
        store.close()
        with self.assertRaises(ClosedEventStoreError):
            store.read_after()

    def test_corrupt_payload_and_schema_fail_clearly(self) -> None:
        with SqliteEventStore(self.path) as store:
            store.append(uncommitted(1, every_draft()[0]))
        connection = sqlite3.connect(self.path)
        connection.execute("UPDATE events SET payload_json = '{not json}'")
        connection.commit()
        connection.close()

        with (
            SqliteEventStore(self.path) as store,
            self.assertRaises(CorruptEventStoreError),
        ):
            store.read_after()

        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA user_version = 99")
        connection.commit()
        connection.close()
        with self.assertRaisesRegex(CorruptEventStoreError, "schema version 99"):
            SqliteEventStore(self.path)


if __name__ == "__main__":
    unittest.main()
