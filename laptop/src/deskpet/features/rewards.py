"""Pure focus reward calculation."""

from dataclasses import dataclass

from deskpet.core.commands import Accepted, Decision, Rejected
from deskpet.core.events import EventSource, FocusRewardGranted
from deskpet.core.models import GameState, KeyboardSummary, RejectionCode, level_for_xp


@dataclass(frozen=True, slots=True)
class RewardPolicy:
    version: int
    xp_per_focus_minute: int
    yarn_minutes_per_unit: int
    chain_xp_percent: int
    chain_yarn_per_step: int
    keyboard_one_yarn_keypresses: int
    keyboard_two_yarn_keypresses: int

    def __post_init__(self) -> None:
        if self.version <= 0 or self.xp_per_focus_minute <= 0:
            raise ValueError("reward version and XP rate must be positive")
        if self.yarn_minutes_per_unit <= 0:
            raise ValueError("yarn_minutes_per_unit must be positive")
        if self.chain_xp_percent < 0 or self.chain_yarn_per_step < 0:
            raise ValueError("chain bonuses must be nonnegative")
        if self.keyboard_one_yarn_keypresses <= 0 or (
            self.keyboard_two_yarn_keypresses <= self.keyboard_one_yarn_keypresses
        ):
            raise ValueError("keyboard reward thresholds must be positive and increase")


def decide(
    state: GameState,
    focus_session_id: str,
    focus_minutes: int,
    chain_number: int,
    policy: RewardPolicy,
    keyboard: KeyboardSummary | None = None,
) -> Decision:
    """Return one fully resolved, deduplicated completion reward."""
    progression = state.progression
    if progression is None or state.pending_break is None:
        return Rejected(RejectionCode.UNAVAILABLE)
    if state.pending_break.parent_focus_id != focus_session_id:
        return Rejected(RejectionCode.UNAVAILABLE)
    if focus_minutes <= 0 or chain_number <= 0:
        raise ValueError("focus_minutes and chain_number must be positive")

    base_xp = focus_minutes * policy.xp_per_focus_minute
    chain_xp = base_xp * policy.chain_xp_percent * (chain_number - 1) // 100
    base_yarn = (focus_minutes + policy.yarn_minutes_per_unit - 1) // (
        policy.yarn_minutes_per_unit
    )
    chain_yarn = (chain_number - 1) * policy.chain_yarn_per_step
    keyboard_enabled = keyboard is not None
    keyboard_available = keyboard.available if keyboard is not None else False
    keypresses = keyboard.keypress_count if keyboard_available and keyboard else 0
    keyboard_yarn = (
        2
        if keypresses >= policy.keyboard_two_yarn_keypresses
        else int(keypresses >= policy.keyboard_one_yarn_keypresses)
    )
    total_xp_after = progression.total_xp + base_xp + chain_xp
    yarn_after = progression.yarn_balance + base_yarn + chain_yarn + keyboard_yarn
    level_after = level_for_xp(
        total_xp_after, progression.xp_per_level, progression.xp_level_increment
    )
    return Accepted(
        FocusRewardGranted(
            source=EventSource.SYSTEM,
            dedupe_key=f"focus-reward:{focus_session_id}",
            focus_session_id=focus_session_id,
            policy_version=policy.version,
            chain_number=chain_number,
            focus_minutes=focus_minutes,
            base_xp=base_xp,
            chain_xp=chain_xp,
            base_yarn=base_yarn,
            chain_yarn=chain_yarn,
            keyboard_enabled=keyboard_enabled,
            keyboard_available=keyboard_available,
            keyboard_keypresses=keypresses,
            keyboard_yarn=keyboard_yarn,
            total_xp_before=progression.total_xp,
            total_xp_after=total_xp_after,
            level_before=progression.level,
            level_after=level_after,
            yarn_before=progression.yarn_balance,
            yarn_after=yarn_after,
        )
    )
