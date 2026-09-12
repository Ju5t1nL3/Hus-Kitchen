"""Contract-level tests for the M04 domain foundation."""

import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

from deskpet.core.commands import Accepted
from deskpet.core.events import (
    EVENT_SCHEMA_VERSION,
    EventSource,
    FocusSessionStarted,
    UncommittedEvent,
)
from deskpet.core.models import (
    BreakOffer,
    BreakTerms,
    ClockReading,
    FocusTerms,
    GameState,
    Session,
    SessionKind,
    SessionStatus,
)
from deskpet.core.ports import Clock


class StubClock:
    def read(self) -> ClockReading:
        return ClockReading(
            utc=datetime(2026, 9, 12, tzinfo=UTC),
            monotonic_ms=100,
            resumed=False,
        )


_CLOCK: Clock = StubClock()


def focus_terms() -> FocusTerms:
    return FocusTerms(
        duration_seconds=1_500,
        break_seconds=300,
        grace_active_ms=60_000,
        sad_seconds=30,
        happy_seconds=30,
        report_timezone="America/Chicago",
    )


class ModelContractTests(unittest.TestCase):
    def test_records_are_immutable(self) -> None:
        terms = focus_terms()

        with self.assertRaises(FrozenInstanceError):
            terms.duration_seconds = 300  # type: ignore[misc]

    def test_session_kind_must_match_terms(self) -> None:
        with self.assertRaisesRegex(ValueError, "kind and terms"):
            Session(
                id="focus-1",
                kind=SessionKind.FOCUS,
                terms=BreakTerms(300, "focus-0", "America/Chicago"),
                status=SessionStatus.RUNNING,
                committed_active_ms=0,
            )

    def test_state_cannot_have_session_and_break_offer(self) -> None:
        session = Session(
            id="focus-1",
            kind=SessionKind.FOCUS,
            terms=focus_terms(),
            status=SessionStatus.RUNNING,
            committed_active_ms=0,
        )

        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            GameState(
                user_id="user-1",
                pet_id="pet-1",
                active_session=session,
                pending_break=BreakOffer("focus-1", 300, "America/Chicago"),
            )

    def test_clock_requires_timezone_aware_utc(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            ClockReading(
                utc=datetime(2026, 9, 12),
                monotonic_ms=0,
                resumed=False,
            )

    def test_clock_protocol_is_structural(self) -> None:
        self.assertEqual(_CLOCK.read().monotonic_ms, 100)


class EventContractTests(unittest.TestCase):
    def test_session_event_fixes_kind_and_terms(self) -> None:
        draft = FocusSessionStarted(
            source=EventSource.SYSTEM,
            dedupe_key="session-start:focus-1",
            session_id="focus-1",
            terms=focus_terms(),
        )

        self.assertEqual(draft.event_type, "session_started")
        self.assertIs(draft.kind, SessionKind.FOCUS)
        self.assertIsInstance(Accepted(draft).event, FocusSessionStarted)

    def test_uncommitted_event_uses_schema_v2(self) -> None:
        from uuid import UUID

        draft = FocusSessionStarted(
            source=EventSource.SYSTEM,
            dedupe_key="session-start:focus-1",
            session_id="focus-1",
            terms=focus_terms(),
        )
        event = UncommittedEvent(
            event_id=UUID("00000000-0000-0000-0000-000000000001"),
            occurred_at=datetime(2026, 9, 12, tzinfo=UTC),
            user_id="user-1",
            device_id="device-1",
            draft=draft,
        )

        self.assertEqual(event.schema_version, EVENT_SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
