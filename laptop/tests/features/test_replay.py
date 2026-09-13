"""Tests for pure event replay and incremental state reduction."""

import unittest
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from deskpet.core.events import (
    BreakSessionStarted,
    BreakSkipped,
    DomainEvent,
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
    GameState,
    Reaction,
    ReactionMood,
    SessionStatus,
)
from deskpet.features.replay import ReplayError, apply_event, rebuild

NOW = datetime(2026, 9, 13, 4, 30, tzinfo=UTC)
TERMS = FocusTerms(300, 60, 60_000, 30, 30, "America/Chicago")


def committed(seq: int, draft: EventDraft, *, user_id: str = "user-1") -> DomainEvent:
    return DomainEvent(
        seq,
        UncommittedEvent(
            event_id=UUID(int=seq),
            occurred_at=NOW + timedelta(seconds=seq),
            user_id=user_id,
            device_id="device-1",
            draft=draft,
        ),
    )


def created(seq: int = 1) -> DomainEvent:
    return committed(
        seq,
        PetCreated(
            source=EventSource.SYSTEM,
            dedupe_key="pet-created",
            pet_id="pet-1",
        ),
    )


def started(seq: int = 2, session_id: str = "focus-1") -> DomainEvent:
    return committed(
        seq,
        FocusSessionStarted(
            source=EventSource.SYSTEM,
            dedupe_key=f"session-start:{session_id}",
            session_id=session_id,
            terms=TERMS,
        ),
    )


class ReplayHappyPathTests(unittest.TestCase):
    def test_progression_initialization_is_durable_and_single_use(self) -> None:
        initialized = committed(
            2,
            ProgressionInitialized(
                source=EventSource.SYSTEM,
                dedupe_key="progression-initialized",
                policy_version=1,
                starting_yarn=10,
                xp_per_level=100,
            ),
        )

        state = rebuild((created(), initialized))

        self.assertIsNotNone(state)
        assert state is not None
        self.assertIsNotNone(state.progression)
        assert state.progression is not None
        self.assertEqual(state.progression.yarn_balance, 10)
        self.assertEqual(state.progression.level, 1)
        with self.assertRaisesRegex(ReplayError, "only be initialized once"):
            apply_event(state, committed(3, initialized.event.draft))

    def test_incremental_and_rebuilt_state_match(self) -> None:
        happy = Reaction(ReactionMood.HAPPY, NOW + timedelta(seconds=40))
        offer = BreakOffer("focus-1", 60, "America/Chicago")
        events = (
            created(),
            started(),
            committed(
                3,
                FocusSessionPaused(
                    source=EventSource.SYSTEM,
                    dedupe_key="button:c:1",
                    session_id="focus-1",
                    active_ms=45_000,
                ),
            ),
            committed(
                4,
                FocusSessionResumed(
                    source=EventSource.SYSTEM,
                    dedupe_key="button:c:2",
                    session_id="focus-1",
                    active_ms=45_000,
                ),
            ),
            committed(
                5,
                FocusSessionCompleted(
                    source=EventSource.SYSTEM,
                    dedupe_key="session-terminal:focus-1",
                    session_id="focus-1",
                    active_ms=300_000,
                    credit_date=date(2026, 9, 12),
                    break_offer=offer,
                    reaction=happy,
                ),
            ),
            committed(
                6,
                BreakSessionStarted(
                    source=EventSource.SYSTEM,
                    dedupe_key="break-choice:focus-1",
                    session_id="break-1",
                    terms=BreakTerms(60, "focus-1", "America/Chicago"),
                ),
            ),
        )
        incremental: GameState | None = None
        snapshots: list[GameState] = []
        for event in events:
            incremental = apply_event(incremental, event)
            snapshots.append(incremental)

        rebuilt = rebuild(events)

        self.assertEqual(rebuilt, incremental)
        self.assertIsNotNone(rebuilt)
        assert rebuilt is not None
        self.assertEqual(rebuilt.last_seq, 6)
        self.assertEqual(rebuilt.focus_dates, frozenset({date(2026, 9, 12)}))
        self.assertEqual(rebuilt.latest_reaction, happy)
        assert rebuilt.active_session is not None
        self.assertEqual(rebuilt.active_session.id, "break-1")
        self.assertIsNone(rebuilt.pending_break)
        self.assertIsNone(snapshots[0].active_session)
        assert snapshots[1].active_session is not None
        self.assertEqual(snapshots[1].active_session.status, SessionStatus.RUNNING)
        assert snapshots[2].active_session is not None
        self.assertEqual(snapshots[2].active_session.status, SessionStatus.PAUSED)

    def test_feed_replaces_latest_reaction_without_mutating_input(self) -> None:
        original = apply_event(None, created())
        content = Reaction(ReactionMood.CONTENT, NOW + timedelta(seconds=20))
        event = committed(
            2,
            PetFed(
                source=EventSource.LOCAL_CONTROLS,
                dedupe_key="button:c:1",
                food_id="basic",
                reaction=content,
            ),
        )

        updated = apply_event(original, event)

        self.assertIsNone(original.latest_reaction)
        self.assertEqual(updated.latest_reaction, content)
        self.assertEqual(updated.last_seq, 2)

    def test_null_terminal_reaction_keeps_newest_reaction_candidate(self) -> None:
        content = Reaction(ReactionMood.CONTENT, NOW + timedelta(seconds=20))
        state = apply_event(None, created())
        state = apply_event(
            state,
            committed(
                2,
                PetFed(
                    source=EventSource.LOCAL_CONTROLS,
                    dedupe_key="button:c:1",
                    food_id="basic",
                    reaction=content,
                ),
            ),
        )
        state = apply_event(state, started(3))

        ended = apply_event(
            state,
            committed(
                4,
                FocusSessionEnded(
                    source=EventSource.SYSTEM,
                    dedupe_key="session-terminal:focus-1",
                    session_id="focus-1",
                    active_ms=10_000,
                    reason=EndReason.USER_GRACE,
                    reaction=None,
                ),
            ),
        )

        self.assertEqual(ended.latest_reaction, content)

    def test_empty_history_rebuilds_to_none(self) -> None:
        self.assertIsNone(rebuild(()))


class ReplayValidationTests(unittest.TestCase):
    def test_history_must_start_once_with_pet_created(self) -> None:
        with self.assertRaisesRegex(ReplayError, "begin with pet_created"):
            rebuild((started(1),))
        with self.assertRaisesRegex(ReplayError, "more than one"):
            rebuild((created(), created(2)))

    def test_sequence_and_user_must_match(self) -> None:
        state = apply_event(None, created(5))
        with self.assertRaisesRegex(ReplayError, "strictly increasing"):
            apply_event(state, started(5))
        with self.assertRaisesRegex(ReplayError, "user_id"):
            apply_event(state, committed(6, started().event.draft, user_id="user-2"))

    def test_pause_resume_and_completion_validate_progress(self) -> None:
        state = rebuild((created(), started()))
        assert state is not None
        paused = apply_event(
            state,
            committed(
                3,
                FocusSessionPaused(
                    source=EventSource.SYSTEM,
                    dedupe_key="button:c:1",
                    session_id="focus-1",
                    active_ms=20_000,
                ),
            ),
        )
        with self.assertRaisesRegex(ReplayError, "paused value"):
            apply_event(
                paused,
                committed(
                    4,
                    FocusSessionResumed(
                        source=EventSource.SYSTEM,
                        dedupe_key="button:c:2",
                        session_id="focus-1",
                        active_ms=20_001,
                    ),
                ),
            )
        with self.assertRaisesRegex(ReplayError, "must be running"):
            apply_event(
                paused,
                committed(
                    4,
                    FocusSessionCompleted(
                        source=EventSource.SYSTEM,
                        dedupe_key="session-terminal:focus-1",
                        session_id="focus-1",
                        active_ms=300_000,
                        credit_date=date(2026, 9, 12),
                        break_offer=BreakOffer("focus-1", 60, "America/Chicago"),
                        reaction=Reaction(
                            ReactionMood.HAPPY, NOW + timedelta(seconds=30)
                        ),
                    ),
                ),
            )

    def test_focus_end_reason_must_match_grace_and_reaction(self) -> None:
        state = rebuild((created(), started()))
        assert state is not None
        invalid = committed(
            3,
            FocusSessionEnded(
                source=EventSource.SYSTEM,
                dedupe_key="session-terminal:focus-1",
                session_id="focus-1",
                active_ms=60_000,
                reason=EndReason.USER_GRACE,
                reaction=None,
            ),
        )

        with self.assertRaisesRegex(ReplayError, "user_grace"):
            apply_event(state, invalid)

    def test_break_start_and_skip_must_match_offer(self) -> None:
        state = apply_event(None, created())
        with self.assertRaisesRegex(ReplayError, "pending break offer"):
            apply_event(
                state,
                committed(
                    2,
                    BreakSessionStarted(
                        source=EventSource.SYSTEM,
                        dedupe_key="break-choice:focus-1",
                        session_id="break-1",
                        terms=BreakTerms(60, "focus-1", "America/Chicago"),
                    ),
                ),
            )
        with self.assertRaisesRegex(ReplayError, "pending offer"):
            apply_event(
                state,
                committed(
                    2,
                    BreakSkipped(
                        source=EventSource.SYSTEM,
                        dedupe_key="break-choice:focus-1",
                        parent_focus_id="focus-1",
                    ),
                ),
            )


if __name__ == "__main__":
    unittest.main()
