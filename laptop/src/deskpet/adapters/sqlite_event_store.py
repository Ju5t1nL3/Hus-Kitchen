"""SQLite-backed append-only event store with exclusive writer ownership."""

import json
import os
import sqlite3
from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import BinaryIO, TypedDict, assert_never, cast
from uuid import UUID

from deskpet.core.events import (
    EVENT_SCHEMA_VERSION,
    BreakSessionCompleted,
    BreakSessionEnded,
    BreakSessionStarted,
    BreakSkipped,
    DomainEvent,
    EndReason,
    EventDraft,
    EventSource,
    FocusRewardGranted,
    FocusSessionCompleted,
    FocusSessionEnded,
    FocusSessionPaused,
    FocusSessionResumed,
    FocusSessionStarted,
    ItemPurchasedAndFed,
    PetComforted,
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
    SessionKind,
)
from deskpet.core.ports import AppendResult, EventStoreError

type JsonValue = (
    None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
)
type JsonObject = dict[str, JsonValue]


class _DraftMetadata(TypedDict):
    source: EventSource
    dedupe_key: str


_SCHEMA_VERSION = 2
_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    schema_version INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    user_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    source TEXT NOT NULL,
    dedupe_key TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE (user_id, source, dedupe_key)
)
"""
_SELECT_COLUMNS = """
seq, event_id, schema_version, event_type, occurred_at,
user_id, device_id, source, dedupe_key, payload_json
"""


class StorageError(EventStoreError):
    """Base class for operational event-store failures."""


class WriterLockError(StorageError):
    """Raised when another writable store owns this database path."""


class EventConflictError(StorageError):
    """Raised when an event ID or semantic operation is reused differently."""


class CorruptEventStoreError(StorageError):
    """Raised when stored schema or event data cannot be trusted."""


class ClosedEventStoreError(StorageError):
    """Raised when a closed store is used."""


class SqliteEventStore:
    """Transactional EventStore implementation; one writable owner per path."""

    def __init__(self, path: Path, *, writable: bool = True) -> None:
        self._path = path.resolve()
        self._writable = writable
        self._lock: _WriterLock | None = None
        self._connection: sqlite3.Connection | None = None
        try:
            if writable:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                self._lock = _WriterLock(self._path)
                self._lock.acquire()
                self._connection = sqlite3.connect(self._path)
                self._initialize_schema()
            else:
                uri = f"{self._path.as_uri()}?mode=ro"
                self._connection = sqlite3.connect(uri, uri=True)
                self._verify_schema()
        except WriterLockError:
            self._release_resources()
            raise
        except (OSError, sqlite3.Error) as error:
            self._release_resources()
            raise StorageError(
                f"cannot open event store {self._path}: {error}"
            ) from error
        except CorruptEventStoreError:
            self._release_resources()
            raise

    def append(self, event: UncommittedEvent) -> AppendResult:
        connection = self._require_open()
        if not self._writable:
            raise StorageError("event store is read-only")
        encoded = _encode_draft(event.draft)
        values = (
            str(event.event_id),
            event.schema_version,
            event.draft.event_type,
            _format_datetime(event.occurred_at),
            event.user_id,
            event.device_id,
            event.draft.source.value,
            event.draft.dedupe_key,
            json.dumps(encoded, separators=(",", ":"), sort_keys=True),
        )
        try:
            with connection:
                cursor = connection.execute(
                    """
                    INSERT INTO events (
                        event_id, schema_version, event_type, occurred_at,
                        user_id, device_id, source, dedupe_key, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    values,
                )
                seq = cursor.lastrowid
            if seq is None:
                raise StorageError("SQLite did not return an event sequence")
            return AppendResult(True, DomainEvent(seq, event))
        except sqlite3.IntegrityError:
            return self._resolve_duplicate(event)
        except sqlite3.Error as error:
            raise StorageError(f"cannot append event: {error}") from error

    def read_after(self, seq: int = 0) -> tuple[DomainEvent, ...]:
        if seq < 0:
            raise ValueError("seq must be nonnegative")
        connection = self._require_open()
        try:
            rows = connection.execute(
                f"SELECT {_SELECT_COLUMNS} FROM events WHERE seq > ? ORDER BY seq",
                (seq,),
            ).fetchall()
            return tuple(_decode_row(row) for row in rows)
        except CorruptEventStoreError:
            raise
        except (sqlite3.Error, TypeError, ValueError) as error:
            raise CorruptEventStoreError(
                f"cannot decode event history: {error}"
            ) from error

    def close(self) -> None:
        self._release_resources()

    def _initialize_schema(self) -> None:
        connection = self._require_open()
        version = _pragma_user_version(connection)
        if version not in {0, _SCHEMA_VERSION}:
            raise CorruptEventStoreError(
                f"unsupported SQLite schema version {version}; expected {_SCHEMA_VERSION}"
            )
        connection.execute(_CREATE_SQL)
        self._verify_event_table()
        if version == 0:
            connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
            connection.commit()

    def _verify_schema(self) -> None:
        connection = self._require_open()
        version = _pragma_user_version(connection)
        if version != _SCHEMA_VERSION:
            raise CorruptEventStoreError(
                f"unsupported SQLite schema version {version}; expected {_SCHEMA_VERSION}"
            )
        self._verify_event_table()

    def _verify_event_table(self) -> None:
        try:
            self._require_open().execute(
                f"SELECT {_SELECT_COLUMNS} FROM events LIMIT 0"
            )
        except sqlite3.Error as error:
            raise CorruptEventStoreError(
                "event table is missing or incompatible"
            ) from error

    def _resolve_duplicate(self, proposed: UncommittedEvent) -> AppendResult:
        connection = self._require_open()
        try:
            rows = connection.execute(
                f"""
                SELECT {_SELECT_COLUMNS} FROM events
                WHERE event_id = ? OR (user_id = ? AND source = ? AND dedupe_key = ?)
                ORDER BY seq
                """,
                (
                    str(proposed.event_id),
                    proposed.user_id,
                    proposed.draft.source.value,
                    proposed.draft.dedupe_key,
                ),
            ).fetchall()
            existing = tuple(_decode_row(row) for row in rows)
        except (sqlite3.Error, TypeError, ValueError) as error:
            raise StorageError(f"cannot resolve duplicate event: {error}") from error
        if len(existing) != 1 or not _same_semantic_event(existing[0].event, proposed):
            raise EventConflictError(
                "event ID or semantic operation already belongs to different data"
            )
        return AppendResult(False, existing[0])

    def _require_open(self) -> sqlite3.Connection:
        if self._connection is None:
            raise ClosedEventStoreError("event store is closed")
        return self._connection

    def _release_resources(self) -> None:
        connection = self._connection
        lock = self._lock
        self._connection = None
        self._lock = None
        try:
            if connection is not None:
                connection.close()
        finally:
            if lock is not None:
                lock.release()

    def __enter__(self) -> SqliteEventStore:
        self._require_open()
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


class _WriterLock:
    def __init__(self, database_path: Path) -> None:
        self._path = database_path.with_name(f"{database_path.name}.lock")
        self._file: BinaryIO | None = None

    def acquire(self) -> None:
        lock_file = self._path.open("a+b")
        lock_file.seek(0)
        if lock_file.read(1) == b"":
            lock_file.write(b"0")
            lock_file.flush()
        lock_file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError) as error:
            lock_file.close()
            raise WriterLockError(
                f"another writer owns event store {self._path}"
            ) from error
        self._file = lock_file

    def release(self) -> None:
        lock_file = self._file
        if lock_file is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        finally:
            lock_file.close()
            self._file = None


def _pragma_user_version(connection: sqlite3.Connection) -> int:
    row = connection.execute("PRAGMA user_version").fetchone()
    if row is None or not isinstance(row[0], int):
        raise CorruptEventStoreError("cannot read SQLite schema version")
    return row[0]


def _same_semantic_event(left: UncommittedEvent, right: UncommittedEvent) -> bool:
    return (
        left.schema_version == right.schema_version
        and left.user_id == right.user_id
        and left.device_id == right.device_id
        and left.draft == right.draft
    )


def _encode_draft(draft: EventDraft) -> JsonObject:
    match draft:
        case PetCreated():
            return {"pet_id": draft.pet_id}
        case ProgressionInitialized():
            return {
                "policy_version": draft.policy_version,
                "starting_yarn": draft.starting_yarn,
                "xp_per_level": draft.xp_per_level,
                "xp_level_increment": draft.xp_level_increment,
            }
        case PetFed():
            return {
                "food_id": draft.food_id,
                "reaction": _encode_reaction(draft.reaction),
            }
        case ItemPurchasedAndFed():
            return {
                "item_id": draft.item_id,
                "price_paid": draft.price_paid,
                "yarn_balance_after": draft.yarn_balance_after,
                "reaction": _encode_reaction(draft.reaction),
            }
        case PetComforted():
            return {"reaction": _encode_reaction(draft.reaction)}
        case FocusRewardGranted():
            return {
                "focus_session_id": draft.focus_session_id,
                "policy_version": draft.policy_version,
                "chain_number": draft.chain_number,
                "focus_minutes": draft.focus_minutes,
                "base_xp": draft.base_xp,
                "chain_xp": draft.chain_xp,
                "base_yarn": draft.base_yarn,
                "chain_yarn": draft.chain_yarn,
                "total_xp_before": draft.total_xp_before,
                "total_xp_after": draft.total_xp_after,
                "level_before": draft.level_before,
                "level_after": draft.level_after,
                "yarn_before": draft.yarn_before,
                "yarn_after": draft.yarn_after,
            }
        case FocusSessionStarted():
            return {
                "session_id": draft.session_id,
                "kind": draft.kind.value,
                "terms": _encode_focus_terms(draft.terms),
            }
        case BreakSessionStarted():
            return {
                "session_id": draft.session_id,
                "kind": draft.kind.value,
                "terms": _encode_break_terms(draft.terms),
            }
        case FocusSessionPaused() | FocusSessionResumed():
            return {
                "session_id": draft.session_id,
                "kind": draft.kind.value,
                "active_ms": draft.active_ms,
            }
        case FocusSessionCompleted():
            return {
                "session_id": draft.session_id,
                "kind": draft.kind.value,
                "active_ms": draft.active_ms,
                "credit_date": draft.credit_date.isoformat(),
                "break_offer": _encode_break_offer(draft.break_offer),
                "reaction": _encode_reaction(draft.reaction),
            }
        case BreakSessionCompleted():
            return {
                "session_id": draft.session_id,
                "kind": draft.kind.value,
                "active_ms": draft.active_ms,
            }
        case FocusSessionEnded():
            return {
                "session_id": draft.session_id,
                "kind": draft.kind.value,
                "active_ms": draft.active_ms,
                "reason": draft.reason.value,
                "reaction": None
                if draft.reaction is None
                else _encode_reaction(draft.reaction),
            }
        case BreakSessionEnded():
            return {
                "session_id": draft.session_id,
                "kind": draft.kind.value,
                "active_ms": draft.active_ms,
                "reason": draft.reason.value,
            }
        case BreakSkipped():
            return {"parent_focus_id": draft.parent_focus_id}
        case _ as unreachable:
            assert_never(unreachable)


def _encode_reaction(value: Reaction) -> JsonObject:
    return {"mood": value.mood.value, "expires_at": _format_datetime(value.expires_at)}


def _encode_focus_terms(value: FocusTerms) -> JsonObject:
    return {
        "duration_seconds": value.duration_seconds,
        "break_seconds": value.break_seconds,
        "grace_active_ms": value.grace_active_ms,
        "sad_seconds": value.sad_seconds,
        "happy_seconds": value.happy_seconds,
        "report_timezone": value.report_timezone,
    }


def _encode_break_terms(value: BreakTerms) -> JsonObject:
    return {
        "duration_seconds": value.duration_seconds,
        "parent_focus_id": value.parent_focus_id,
        "report_timezone": value.report_timezone,
    }


def _encode_break_offer(value: BreakOffer) -> JsonObject:
    return {
        "parent_focus_id": value.parent_focus_id,
        "duration_seconds": value.duration_seconds,
        "report_timezone": value.report_timezone,
    }


def _decode_row(row: tuple[object, ...]) -> DomainEvent:
    if len(row) != 10:
        raise CorruptEventStoreError("stored event row has the wrong column count")
    seq = _integer(row[0], "seq")
    event_id = UUID(_string(row[1], "event_id"))
    schema_version = _integer(row[2], "schema_version")
    if schema_version != EVENT_SCHEMA_VERSION:
        raise CorruptEventStoreError(
            f"unsupported event version {schema_version} at seq {seq}"
        )
    event_type = _string(row[3], "event_type")
    occurred_at = _datetime(_string(row[4], "occurred_at"), "occurred_at")
    user_id = _string(row[5], "user_id")
    device_id = _string(row[6], "device_id")
    source = EventSource(_string(row[7], "source"))
    dedupe_key = _string(row[8], "dedupe_key")
    payload_raw = cast(JsonValue, json.loads(_string(row[9], "payload_json")))
    payload = _object(payload_raw, "payload")
    draft = _decode_draft(event_type, source, dedupe_key, payload)
    return DomainEvent(
        seq,
        UncommittedEvent(event_id, occurred_at, user_id, device_id, draft),
    )


def _decode_draft(
    event_type: str,
    source: EventSource,
    dedupe_key: str,
    payload: Mapping[str, JsonValue],
) -> EventDraft:
    metadata = _DraftMetadata(source=source, dedupe_key=dedupe_key)
    if event_type == "pet_created":
        _keys(payload, {"pet_id"})
        return PetCreated(**metadata, pet_id=_text_field(payload, "pet_id"))
    if event_type == "progression_initialized":
        _keys(
            payload,
            {
                "policy_version",
                "starting_yarn",
                "xp_per_level",
                "xp_level_increment",
            },
        )
        return ProgressionInitialized(
            **metadata,
            policy_version=_int_field(payload, "policy_version"),
            starting_yarn=_int_field(payload, "starting_yarn"),
            xp_per_level=_int_field(payload, "xp_per_level"),
            xp_level_increment=_int_field(payload, "xp_level_increment"),
        )
    if event_type == "pet_fed":
        _keys(payload, {"food_id", "reaction"})
        return PetFed(
            **metadata,
            food_id=_text_field(payload, "food_id"),
            reaction=_reaction(payload["reaction"]),
        )
    if event_type == "item_purchased_and_fed":
        _keys(
            payload,
            {"item_id", "price_paid", "yarn_balance_after", "reaction"},
        )
        return ItemPurchasedAndFed(
            **metadata,
            item_id=_text_field(payload, "item_id"),
            price_paid=_int_field(payload, "price_paid"),
            yarn_balance_after=_int_field(payload, "yarn_balance_after"),
            reaction=_reaction(payload["reaction"]),
        )
    if event_type == "pet_comforted":
        _keys(payload, {"reaction"})
        return PetComforted(**metadata, reaction=_reaction(payload["reaction"]))
    if event_type == "focus_reward_granted":
        fields = {
            "focus_session_id",
            "policy_version",
            "chain_number",
            "focus_minutes",
            "base_xp",
            "chain_xp",
            "base_yarn",
            "chain_yarn",
            "total_xp_before",
            "total_xp_after",
            "level_before",
            "level_after",
            "yarn_before",
            "yarn_after",
        }
        _keys(payload, fields)
        return FocusRewardGranted(
            **metadata,
            focus_session_id=_text_field(payload, "focus_session_id"),
            policy_version=_int_field(payload, "policy_version"),
            chain_number=_int_field(payload, "chain_number"),
            focus_minutes=_int_field(payload, "focus_minutes"),
            base_xp=_int_field(payload, "base_xp"),
            chain_xp=_int_field(payload, "chain_xp"),
            base_yarn=_int_field(payload, "base_yarn"),
            chain_yarn=_int_field(payload, "chain_yarn"),
            total_xp_before=_int_field(payload, "total_xp_before"),
            total_xp_after=_int_field(payload, "total_xp_after"),
            level_before=_int_field(payload, "level_before"),
            level_after=_int_field(payload, "level_after"),
            yarn_before=_int_field(payload, "yarn_before"),
            yarn_after=_int_field(payload, "yarn_after"),
        )
    if event_type == "break_skipped":
        _keys(payload, {"parent_focus_id"})
        return BreakSkipped(
            **metadata, parent_focus_id=_text_field(payload, "parent_focus_id")
        )

    kind = SessionKind(_text_field(payload, "kind"))
    session_id = _text_field(payload, "session_id")
    if event_type == "session_started":
        _keys(payload, {"session_id", "kind", "terms"})
        terms = _object(payload["terms"], "terms")
        if kind is SessionKind.FOCUS:
            return FocusSessionStarted(
                **metadata, session_id=session_id, terms=_focus_terms(terms)
            )
        return BreakSessionStarted(
            **metadata, session_id=session_id, terms=_break_terms(terms)
        )
    if event_type in {"session_paused", "session_resumed"}:
        _keys(payload, {"session_id", "kind", "active_ms"})
        if kind is not SessionKind.FOCUS:
            raise CorruptEventStoreError(
                f"{event_type} is only valid for focus sessions"
            )
        active_ms = _int_field(payload, "active_ms")
        if event_type == "session_paused":
            return FocusSessionPaused(
                **metadata, session_id=session_id, active_ms=active_ms
            )
        return FocusSessionResumed(
            **metadata, session_id=session_id, active_ms=active_ms
        )
    if event_type == "session_completed":
        if kind is SessionKind.BREAK:
            _keys(payload, {"session_id", "kind", "active_ms"})
            return BreakSessionCompleted(
                **metadata,
                session_id=session_id,
                active_ms=_int_field(payload, "active_ms"),
            )
        _keys(
            payload,
            {
                "session_id",
                "kind",
                "active_ms",
                "credit_date",
                "break_offer",
                "reaction",
            },
        )
        return FocusSessionCompleted(
            **metadata,
            session_id=session_id,
            active_ms=_int_field(payload, "active_ms"),
            credit_date=date.fromisoformat(_text_field(payload, "credit_date")),
            break_offer=_break_offer(_object(payload["break_offer"], "break_offer")),
            reaction=_reaction(payload["reaction"]),
        )
    if event_type == "session_ended":
        reason = EndReason(_text_field(payload, "reason"))
        active_ms = _int_field(payload, "active_ms")
        if kind is SessionKind.BREAK:
            _keys(payload, {"session_id", "kind", "active_ms", "reason"})
            return BreakSessionEnded(
                **metadata, session_id=session_id, active_ms=active_ms, reason=reason
            )
        _keys(payload, {"session_id", "kind", "active_ms", "reason", "reaction"})
        raw_reaction = payload["reaction"]
        reaction = None if raw_reaction is None else _reaction(raw_reaction)
        return FocusSessionEnded(
            **metadata,
            session_id=session_id,
            active_ms=active_ms,
            reason=reason,
            reaction=reaction,
        )
    raise CorruptEventStoreError(f"unknown event type: {event_type}")


def _reaction(value: JsonValue) -> Reaction:
    raw = _object(value, "reaction")
    _keys(raw, {"mood", "expires_at"})
    return Reaction(
        ReactionMood(_text_field(raw, "mood")),
        _datetime(_text_field(raw, "expires_at"), "reaction.expires_at"),
    )


def _focus_terms(raw: Mapping[str, JsonValue]) -> FocusTerms:
    fields = {
        "duration_seconds",
        "break_seconds",
        "grace_active_ms",
        "sad_seconds",
        "happy_seconds",
        "report_timezone",
    }
    _keys(raw, fields)
    return FocusTerms(
        *(
            _int_field(raw, key)
            for key in (
                "duration_seconds",
                "break_seconds",
                "grace_active_ms",
                "sad_seconds",
                "happy_seconds",
            )
        ),
        report_timezone=_text_field(raw, "report_timezone"),
    )


def _break_terms(raw: Mapping[str, JsonValue]) -> BreakTerms:
    _keys(raw, {"duration_seconds", "parent_focus_id", "report_timezone"})
    return BreakTerms(
        _int_field(raw, "duration_seconds"),
        _text_field(raw, "parent_focus_id"),
        _text_field(raw, "report_timezone"),
    )


def _break_offer(raw: Mapping[str, JsonValue]) -> BreakOffer:
    _keys(raw, {"parent_focus_id", "duration_seconds", "report_timezone"})
    return BreakOffer(
        _text_field(raw, "parent_focus_id"),
        _int_field(raw, "duration_seconds"),
        _text_field(raw, "report_timezone"),
    )


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("stored datetimes must be timezone-aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _datetime(value: str, name: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CorruptEventStoreError(f"{name} must be timezone-aware")
    return parsed.astimezone(UTC)


def _object(value: JsonValue, name: str) -> Mapping[str, JsonValue]:
    if not isinstance(value, dict):
        raise CorruptEventStoreError(f"{name} must be an object")
    return value


def _keys(value: Mapping[str, JsonValue], expected: set[str]) -> None:
    if set(value) != expected:
        raise CorruptEventStoreError(
            "stored event payload fields do not match its type"
        )


def _text_field(value: Mapping[str, JsonValue], key: str) -> str:
    return _string(value.get(key), key)


def _int_field(value: Mapping[str, JsonValue], key: str) -> int:
    return _integer(value.get(key), key)


def _string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise CorruptEventStoreError(f"{name} must be a nonempty string")
    return value


def _integer(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise CorruptEventStoreError(f"{name} must be an integer")
    return value
