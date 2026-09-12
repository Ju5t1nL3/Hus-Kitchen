# XP, coins and optional activity bonuses — after MVP

This is the first post-MVP milestone, not a change to the current timer/feeding
implementation scope. The [ordered future ideas](nice_to_haves.md) place keyboard
and head tracking first so they can supply its bonuses.

## Agreed behavior

- Add an XP bar and coin total at the top. XP fills toward the next level; it is
  unrelated to the future pixel-art timer visualization.
- Calculate XP and coins when a focus session completes. Gaining a level adds
  bonus coins. The laptop performs all calculations; Pico draws the results.
- More typing can earn bonus coins. Head tracking can estimate focus and earn
  bonus coins. Keyboard and camera each have an independent on/off setting.
- Health, hunger and friendship are permanently removed concepts, not future
  features. Neither sensor can subtract those stats or create replacements.

Proposed defaults: only successful focus sessions qualify, not pauses, breaks or
early endings. Sensor use adds bonuses; disabled/unavailable sensors never reduce
the base reward. These defaults preserve the existing low-stress focus loop.

## Reward calculation

The reward sources are decided; the actual numbers and thresholds are still open.
Keep them in a versioned reward policy in configuration:

```text
session_xp = base_xp(completed_focus_duration)
session_coins = base_coins(completed_focus_duration)
              + typing_bonus(eligible_typing_summary)
              + head_focus_bonus(eligible_head_summary)
new_total_xp = previous_total_xp + session_xp
new_level = level_for(new_total_xp)
coins_awarded = session_coins + level_bonus(previous_level, new_level)
```

This is a proposed formula structure, not chosen rates. Sensor bonuses currently
apply to coins; whether they also increase XP is an open choice. Propose awarding
each crossed level's bonus once if one session spans multiple levels. Level
thresholds must increase, amounts must be nonnegative integers, and rounding and
bonus caps must be explicit. A completed short session and long session must use
the same documented duration policy; do not silently pick fixed/per-minute rates.

## Optional sensing

Keyboard and head tracking run as separate laptop adapters and can be enabled
independently. Proposed default is off until enabled. Turning one off stops its
capture immediately; turning it on does not fabricate data for earlier time.
Permission failure or unavailable hardware yields no bonus from that source.

Collect only during active focus segments, excluding pauses/breaks. Summaries
contain session ID, sample interval, coverage and aggregate measurements. Keyboard
counts activity, not key identities/text. Mouse activity can drive reactions;
whether it earns a bonus is undecided. Head tracking records an estimated oriented/
observed duration and availability, not frames, identity or proof of attention.
Reading and thinking can be productive without typing or facing the camera.

Use only valid, nonoverlapping observed intervals; missing camera observations
are unavailable rather than “not focused.” Keep earlier voluntarily collected
segments eligible if the user disables a sensor later, and record setting changes
so the result is explainable. Do not collect or upload raw input/video. Summary
windows, confidence thresholds, bonus scaling and caps need tuning before release.

## Keep it modular and durable

| Component | Input → output | Owner |
| --- | --- | --- |
| Activity adapters | Enabled active-focus windows → aggregate samples with coverage | adapters/keyboard.py and adapters/head_tracking.py |
| Session aggregator | Valid samples and focus/pause boundaries → final ActivitySummary | features/activity.py |
| Reward calculator | Completion, summary, pinned RewardPolicy, previous totals → RewardBreakdown | features/rewards.py; pure, no hardware imports |
| Progression reducer | Recorded reward → total XP, level and coin balance | Existing replay dispatch plus progression records |
| Presenter | Progression totals → top XP bar/coin display | Laptop presenter; new versioned render fields |

These are future modules, not files to scaffold for MVP. Register new commands
with the existing application; sensors cannot mutate totals directly.

When implementing this milestone, version the event schema and pin reward policy
at focus start, storing effective values as well as the policy version so recovery
does not depend on a later configuration file. Persist the final eligible
ActivitySummary with focus completion.
Then append one rewards_granted event with session ID, component amounts, policy
version, XP/level before/after and level bonus; use a unique reward key per focus
session. Replay applies recorded amounts, never recalculates with current policy.

If completion commits before the reward write and the app crashes, startup grants
any missing eligible reward using its saved summary/policy. Process outstanding
rewards in completion order before new reward decisions so level bonuses are
deterministic. Pre-milestone sessions without pinned policies do not receive
retroactive rewards. Duplicate completions, retries and restarts cannot pay twice.
Only committed rewards update the top bar or trigger reward animations.

## Decisions to review before implementation

1. Base XP/coin rates and duration scaling.
2. Typing/head bonus thresholds, caps and whether bonuses also affect XP.
3. Level thresholds and bonus coins per level, including multiple-level gains.
4. Placement of the new top strip alongside the home clock and timer's small face.
   Keep the center countdown readable; the exact pixel layout is still open.
5. Sensor-summary windows and confidence/coverage rules.

Verify disabled sensors, pause exclusion, missing samples, level crossings and
crash/retry deduplication with fake inputs before testing actual sensors.
