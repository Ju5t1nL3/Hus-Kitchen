# XP, levels, yarn and reward inputs

This is now an approved expansion that must be completed before final MVP
verification. `yarn` is the currency name; do not call it coins in product-facing
code or UI. Health, hunger and friendship remain permanently removed.

## Delivery order

1. Add durable XP, level and yarn state plus the top-screen presentation contract.
2. Replace immediate free feeding with a Feed menu: Food, Drink and Back. Food and
   Drink cost yarn and the chosen item is purchased and fed immediately.
3. Have the user define the complete mood list, triggers, precedence and durations;
   then implement that catalog consistently across laptop and Pico contracts.
4. Decide and implement base XP and yarn for completed focus sessions.
5. Add optional keystroke-count yarn bonuses, then optional camera-attention yarn
   bonuses.
6. Add yarn bonuses for level gains, uninterrupted focus chains and the first
   qualifying completion on a continuing daily streak. Build daily-streak facts
   and the weekly text recap together.
7. Run full fake-device and real-device verification.

[todo.md](todo.md) owns exact task IDs and dependencies. Later steps must not force
earlier code to guess unresolved product values.

## Economy and feeding

GameState retains an immutable `ProgressionState` with nonnegative total XP and
yarn balance, a derived positive level, the recorded XP threshold and its policy
version. The provisional configured foundation is 10 starting yarn and 100 XP per
level. XP advances levels and is not spendable; yarn is.

`progression_initialized` is appended once after `pet_created`. Replay applies its
recorded values rather than current configuration, and its stable dedupe key makes
startup/retry idempotent. Existing histories receive it on their next startup; old
focus sessions receive no retroactive rewards.

Home's Feed action opens a three-button menu:

| Button | Action |
| --- | --- |
| 1 | Buy and feed Food for its displayed yarn price |
| 2 | Buy and feed Drink for its displayed yarn price |
| 3 | Back to Home without an event |

The current direction is an immediate purchase-and-feed operation, not a separate
inventory. One committed event must contain the resolved item, price paid, balance
change and reaction facts needed for deterministic replay. Insufficient yarn is a
rejection: do not feed, animate or mutate state. Item prices remain open choices
and belong in validated configuration.

## Reward calculation

The reward sources are agreed, but rates, thresholds, caps and scaling remain open.
A versioned policy should eventually produce an explainable breakdown shaped like:

```text
base_xp = base_xp_for(completed_focus_duration)
base_yarn = base_yarn_for(completed_focus_duration)
typing_yarn = typing_bonus(eligible_typing_summary)
attention_yarn = attention_bonus(eligible_attention_summary)
chain_yarn = focus_chain_bonus(chain_length)
daily_yarn = daily_streak_bonus(streak_day, first_qualifying_completion)

new_total_xp = previous_total_xp + base_xp
new_level = level_for(new_total_xp)
level_yarn = level_bonus(previous_level, new_level)
total_yarn = base_yarn + typing_yarn + attention_yarn
           + chain_yarn + daily_yarn + level_yarn
```

Only completed focus sessions qualify by default. Pauses, breaks and manually
ended focus sessions do not earn completion rewards. Sensor bonuses add to the
base reward; disabled, unavailable or denied sensors never reduce it. Whether any
non-base source can add XP remains open; do not assume it does.

Award each crossed level bonus exactly once if one completion spans multiple
levels. Define all integer rounding and caps explicitly. A durable reward event is
deduplicated by focus session ID and stores component amounts and before/after
totals; replay applies recorded values instead of recalculating with current config.

## Focus-chain and daily streak meanings

The user describes a focus chain as consecutive completed Pomodoros in the current
run without clicking End. Exact reset behavior for Home, app restart, sleep,
skipped breaks and calendar changes is still open and must be resolved before M30.

The daily bonus applies only to the first qualifying completion of a day when the
user is continuing a daily streak. Exact timezone, minimum streak day and bonus
curve remain open. Store/query enough identity to prevent two completions or a
restart from claiming the same daily bonus.

Weekly recap and bonus code consume the same pure daily/chain queries. The recap
does not award anything itself, and cumulative pause/resume samples must never be
summed as if each were new focused time.

## Optional sensing

Keyboard and camera inputs are independent laptop adapters and independently
opt-in. Capture only during active focus segments, excluding pauses and breaks.

- Keyboard captures counts/timing summaries, never key identities or typed text.
- Camera processing stays local and stores aggregate coverage/attention estimates,
  never frames, video, identity or facial recognition data.
- Missing camera observations mean unavailable, not inattentive.
- Turning a sensor off stops capture immediately and cannot fabricate earlier data.
- Reading and thinking can be productive without typing or facing the camera;
  therefore these signals only add optional yarn.

Summary intervals must be valid and nonoverlapping. Permission failures and device
errors yield zero bonus from that source, never a penalty.

## Modular and durable implementation

| Component | Input → output | Boundary |
| --- | --- | --- |
| Feeding catalog/rules | Item ID, balance, configured price and time → purchase/feed event or rejection | Pure feature code; no UI/SQLite imports |
| Activity adapters | Enabled active-focus windows → aggregate samples with coverage | OS keyboard and local camera adapters |
| Activity aggregator | Samples plus pause/session boundaries → typed session summaries | Pure validation and interval accounting |
| Reward calculator | Completion, summaries, history facts, pinned policy and previous totals → reward breakdown | Pure feature code |
| Progression reducer | Recorded economy/reward events → XP, level and yarn | Existing replay path |
| Presenter | Progression totals and feed catalog → top strip/feed-menu snapshot | Laptop projection only |

Pin the effective reward policy/version to the focus session before sensor samples
or rewards depend on it. If completion commits before its reward event and the app
crashes, startup may grant the missing reward from saved policy and summaries.
Process missing rewards in completion order so level and streak bonuses remain
deterministic. Pre-progression sessions receive no retroactive rewards unless the
user explicitly changes that policy.

## Open decisions

- Food/Drink prices (starting yarn is provisionally 10 and configurable).
- Food/Drink names, reactions and animation/assets.
- Complete mood catalog, triggers, precedence and durations.
- Base XP/yarn rates, duration scaling, rounding and caps.
- Final level thresholds and yarn per crossed level (100 XP/level is provisional).
- Keystroke and attention thresholds, coverage rules and caps.
- Exact focus-chain reset conditions.
- Daily-streak timezone, eligibility and bonus curve.
- Exact strip styling; M24 places it on Home only so timers stay readable.
