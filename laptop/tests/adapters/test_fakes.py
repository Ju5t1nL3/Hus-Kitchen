"""Behavioral tests for deterministic fake resources."""

import unittest
from datetime import UTC, datetime
from uuid import UUID

from deskpet.adapters.fakes import (
    FakeClock,
    FakeDeviceLink,
    FakeEventConflictError,
    FakeEventStore,
    FakeResourceClosedError,
)
from deskpet.core.events import EventSource, PetCreated, UncommittedEvent
from deskpet.core.models import (
    ButtonId,
    ClockReading,
    Mood,
    PublishStatus,
    Screen,
)
from deskpet.core.ports import Clock, DeviceLink, EventStore
from deskpet.core.views import ButtonLabel, RenderSnapshot, Shutdown

NOW = datetime(2026, 9, 12, 14, 0, tzinfo=UTC)


def pet_created(
    *,
    event_id: str = "00000000-0000-0000-0000-000000000001",
    pet_id: str = "pet-1",
) -> UncommittedEvent:
    return UncommittedEvent(
        event_id=UUID(event_id),
        occurred_at=NOW,
        user_id="user-1",
        device_id="device-1",
        draft=PetCreated(
            source=EventSource.SYSTEM,
            dedupe_key="pet-created",
            pet_id=pet_id,
        ),
    )


def home_view() -> RenderSnapshot:
    return RenderSnapshot(
        screen=Screen.HOME,
        control_epoch=1,
        mood=Mood.CALM,
        clock_text="14:00",
        timer_seconds=None,
        paused=False,
        focus_minutes=None,
        break_minutes=None,
        buttons=(ButtonLabel(ButtonId(1), "Feed", True),),
        feedback=None,
    )


class FakeClockTests(unittest.TestCase):
    def test_advance_controls_both_clocks_and_resume_signal(self) -> None:
        fake = FakeClock(ClockReading(NOW, 100, False))
        clock: Clock = fake

        reading = fake.advance(1_500, resumed=True)

        self.assertEqual(clock.read(), reading)
        self.assertEqual(reading.utc, datetime(2026, 9, 12, 14, 0, 1, 500000, UTC))
        self.assertEqual(reading.monotonic_ms, 1_600)
        self.assertTrue(reading.resumed)


class FakeEventStoreTests(unittest.TestCase):
    def test_append_is_idempotent_for_same_semantic_operation(self) -> None:
        fake = FakeEventStore()
        store: EventStore = fake
        first = store.append(pet_created())
        retry = store.append(
            pet_created(event_id="00000000-0000-0000-0000-000000000099")
        )

        self.assertTrue(first.inserted)
        self.assertFalse(retry.inserted)
        self.assertEqual(retry.event, first.event)
        self.assertEqual(tuple(store.read_after()), (first.event,))

    def test_same_operation_with_different_payload_conflicts(self) -> None:
        fake = FakeEventStore()
        fake.append(pet_created())

        with self.assertRaises(FakeEventConflictError):
            fake.append(
                pet_created(
                    event_id="00000000-0000-0000-0000-000000000002",
                    pet_id="different-pet",
                )
            )

    def test_closed_store_rejects_reads_and_writes(self) -> None:
        fake = FakeEventStore()
        fake.close()

        with self.assertRaises(FakeResourceClosedError):
            tuple(fake.read_after())
        with self.assertRaises(FakeResourceClosedError):
            fake.append(pet_created())


class FakeDeviceLinkTests(unittest.TestCase):
    def test_captures_views_and_emits_input(self) -> None:
        received: list[object] = []
        fake = FakeDeviceLink()
        device: DeviceLink = fake
        device.start(received.append)

        status = device.publish(home_view(), revision=1)
        fake.emit(Shutdown())

        self.assertIs(status, PublishStatus.QUEUED)
        self.assertEqual(fake.published[0].revision, 1)
        self.assertEqual(received, [Shutdown()])

    def test_disconnected_device_reports_status_without_capturing(self) -> None:
        fake = FakeDeviceLink(connected=False)

        status = fake.publish(home_view(), revision=1)

        self.assertIs(status, PublishStatus.DISCONNECTED)
        self.assertEqual(fake.published, [])


if __name__ == "__main__":
    unittest.main()
