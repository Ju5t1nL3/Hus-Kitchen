# XP, levels, yarn and reward inputs

This is now an approved expansion that must be completed before final MVP
verification. `yarn` is the currency name; do not call it coins in product-facing
code or UI. Health, hunger and friendship remain permanently removed.

## Delivery order

1. Add durable XP, level and yarn state plus the top-screen presentation contract.
2. Feed opens Jollof Rice (3 yarn), Coffee (2 yarn), and Back. A choice is
   purchased and fed immediately.
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
yarn balance, a derived positive level, the recorded level curve and its policy
version. The configured foundation is 10 starting yarn, a 75-XP first threshold,
and 25 more required XP for each successive level. XP advances levels and is not
spendable; yarn is.

`progression_initialized` is appended once after `pet_created`. Replay applies its
recorded values rather than current configuration, and its stable dedupe key makes
startup/retry idempotent. Existing histories receive it on their next startup; old
focus sessions receive no retroactive rewards.

Home's Feed action opens a three-button menu:

| Button | Action |
| --- | --- |
| 1 | Buy and feed Jollof Rice for 3 yarn |
| 2 | Buy and feed Coffee for 2 yarn |
| 3 | Back to Home without an event |

The current direction is an immediate purchase-and-feed operation, not a separate
inventory. One committed event must contain the resolved item, price paid, balance
change and reaction facts needed for deterministic replay. Insufficient yarn is a
rejection: do not feed, animate or mutate state. Both choices use the shared
three-frame eating animation (`feed` manifest ID) and then set Happy for a
configured 15 seconds.

## Completed-focus rewards

M27 uses this approved, versioned policy. Let `N` be the one-based number of the
completion in the current uninterrupted focus chain:

```text
base_xp = 3 * selected_focus_minutes
chain_xp = floor(base_xp * 15 * (N - 1) / 100)
base_yarn = ceil(selected_focus_minutes / 10)
chain_yarn = N - 1
awarded_xp = base_xp + chain_xp
awarded_yarn = base_yarn + chain_yarn
```

There is no reward cap. Examples: a first 5-minute completion earns 15 XP/1 yarn;
25-minute chain positions 1, 2 and 3 earn 75/3, 86/4 and 97/5; a 60-minute chain
position 3 earns 234/8. Only completed focus sessions qualify. Pauses, breaks and
manually ended focus sessions earn nothing.

The XP required to advance from current `level` is
`75 + 25 * (level - 1)`. Thresholds therefore grow 75, 100, 125, ... with no
maximum level. Keep total XP durably, derive level and within-level progress, and
never use floating-point arithmetic.

The chain continues through Pause, Again from the break offer, or taking the
offered break and selecting Again before leaving its screen. It resets on Home,
completed/quit break into Home, early End, application restart, or recovery
interruption. The current chain is runtime-only; earned XP and yarn are durable.

Production Home displays only level and yarn to keep the small screen calm. Exact
within-level XP remains in the render contract for the development simulator and
diagnostics, but the physical renderer must not draw it. The Party/break-offer
screen shows the just-earned `+XP` and `+yarn` amounts.

Later sensor, daily-streak and crossed-level yarn bonuses extend this breakdown;
they do not change M27's base award. A durable reward event is
deduplicated by focus session ID and stores component amounts and before/after
totals; replay applies recorded values instead of recalculating with current config.

## Focus-chain and daily streak meanings

The M27 focus-chain boundaries are defined above. M30 may add level/daily-streak
yarn components, but must not redefine or double-award the M27 chain components.

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

M28 fixes keyboard rewards at zero below 500 eligible presses, +1 yarn from
500–999, and +2 yarn at 1,000 or more. Two yarn is the per-completion maximum.
Keyboard activity never awards XP. Counts include only active focus segments;
pause, break and ended sessions are excluded. Persist the enabled/available flags,
eligible count and resolved yarn in the reward event, never key identities.

Hold Home button 1 to open Settings. Up cycles Keyboard/Camera, Select toggles the
selected available integration, and Back returns Home. Consent defaults Off and is
saved locally. A camera that cannot be opened is displayed as Unavailable.

M29 samples the camera locally twice per second with OpenCV's bundled frontal-face
Haar cascade. A centered frontal face is an attentive sample; this is a coarse
presence/orientation signal, not eye-gaze tracking or recognition. More than five
continuous active seconds without one selects Working Sad. Failed frame reads are
unknown and reset that continuous-away interval. Rewards require at least 60%
usable observations: 70–89% attentive earns +1 yarn and 90–100% earns +2 yarn.
Camera activity never awards XP and is capped at two yarn per completion.

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

- Final price tuning (current configured values are 3 and 2 yarn).
- Happy artwork may use one or two individual PNG frames; eating uses three.
- Complete mood catalog, triggers, precedence and durations.
- Yarn awarded for crossing levels.
- Keystroke and attention thresholds, coverage rules and caps.
- Daily-streak timezone, eligibility and bonus curve.
- Exact strip styling; M24 places it on Home only so timers stay readable.
