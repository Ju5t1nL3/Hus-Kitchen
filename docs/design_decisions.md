# Decisions, preferences and open questions

Status: planning only. The small-screen emotion-first design below supersedes the
earlier stats/shop proposal. No implementation or hardware verification is claimed.

## User preferences to preserve

- Modular, maintainable, easily updated code with independent hackathon ownership.
- Explicit function inputs/outputs and a precise Pico ↔ laptop contract.
- Short plain-language [overview](overview.md); detailed specs are references.
- Root AGENTS as the entry point; supporting Markdown in docs/.
- Typed laptop code, boundary validation, shared rule ownership and selective
  Twelve-Factor application; see [implementation guidelines](implementation_guidelines.md).
- Existing plans may be improved. Future ideas should inform boundaries without
  requiring their implementation now.
- Adding buttons or changing their functions should be a small, localized change.
- Health/hunger/friendship are permanently removed; do not retain them as future work.
- After MVP, prioritize XP/coins and level bonuses, then optional keyboard/head
  bonuses. Preserve the exact [future-feature order](nice_to_haves.md).
- Four team members are confirmed, but possibly only two will work on software.
  Do not assign roles in advance: contributors pick tasks from [todo.md](todo.md),
  record their handle and update progress/completion there.
- Some board setup is already reported. Inspect and document it before repeating
  work. The user selected CPython 3.14.6 for the laptop, with uv/Ruff/Pyright scoped
  to `laptop/`; tuning and reward/XP-strip layout choices remain open.

## Current product decisions

| Decision | Why |
| --- | --- |
| Home: big pet, top-right clock, Feed/Focus buttons | Fits the small display and keeps actions obvious. |
| Three default physical buttons; configurable bindings and ID-based input | The third button gives most screens a real Back/secondary action (Setup's Back, focus's Time reveal, break's Again) without special-casing button counts; Home and break_running still only bind two and leave the third disabled. |
| Break sessions cannot be paused | Break offers only two actions (Again, Home), both of which end the break; keeping a third pause/resume pair added no value once ending was always one press away. |
| Again: skip/end a break and immediately start a new focus session at the last confirmed duration | Lets a user keep working without revisiting Setup, while remaining an explicit press rather than an automatic continuation. |
| One free food with a separate definition and sprite | Small MVP with room for more foods later. |
| 5–60-minute focus in five-minute steps; default 25, remember last confirmation | Simple adjustable duration. “5s” is interpreted as five-minute increments, as discussed with the user. |
| Break = one-fifth of focus, rounded to whole minutes, minimum one | Transparent proposed product rule; not a universal Pomodoro requirement. |
| Offer a break after completion; do not auto-start | User controls when rest starts; no unattended countdown. |
| Large countdown, small expressive face at top right | Prioritizes readability; removes progress art from MVP. |
| End and Pause/Resume during focus and break | Supports accidental starts and interruptions. |
| Grace below 60 seconds of actual focus; brief sadness after that | Pauses do not consume grace; no lasting punishment. |
| Emotions from saved events and explicit time | Predictable content/happy/sad reactions without hidden numerical stats. |
| Laptop-only streak/weekly text report | Keeps useful history without cluttering the Pico. |
| First post-MVP: top XP bar/coin total, focus-completion XP/coins, level bonus coins | Progression is now the next committed milestone, not an unspecified economy idea. |
| Keyboard and head-tracking coin bonuses with separate on/off settings | Both inputs are priorities; base rewards remain available without sensing. |

Reaction durations (content 20s, happiness 30s, sadness 30s), setup hold-to-back,
and neutral break ending are documented defaults that can be tuned. The exact
screen/control behavior is owned by [MVP goals](features_and_goals.md).

## Architecture decisions retained or revised

| Decision | Consequence |
| --- | --- |
| Laptop owns rules; Pico draws/reports physical gestures | Firmware has no timer, mood or feeding decisions. |
| One state writer with queued USB input/output | Responsive controls without concurrent mutable game state. |
| Pure feature functions and injected resource classes | Test without hardware; keep adapters replaceable. |
| SQLite append-only events | Replay history and enforce one session terminal outcome. |
| Separate GameState, RuntimeState and RenderSnapshot | Saved facts do not depend on a current screen or live clock anchor. |
| Pin timing/reaction terms and resolved expiries in events | Configuration changes do not rewrite existing outcomes. |
| Unified timer feature with focus/break kind | Pause/resume arithmetic is implemented once. |
| Explicit control_epoch in button reports | An old End/Pause cannot activate the new screen after completion. |
| Protocol v2/UI emotions_v1 and event schema v2 | Replaces incompatible, unimplemented stats/shop examples. No migration code is needed yet; incompatible data must not silently load. |
| Neutral end on restart/suspend; restore pending break offers | Supports manual pause/resume while deferring reliable restart-resume. |
| No offline stat decay or emotion penalties | Breaks from the application do not damage the pet. |

## Superseded requirements

Health/hunger/friendship are removed from the product, not deferred. Coins/XP are
the first post-MVP milestone, specified in [progression design](progression_design.md).
The former grouped “deferred MVP” backlog is removed. Pixel-art timer progress is
only future idea #8. The old fixed-duration/no-pause focus flow is also superseded.

Original hardware notes alternated Pico/Pi Zero and LCD/OLED; those choices were
not verified. The plan assumes Pico with the listed LCD behind a replaceable driver.
A future web listener belongs on the laptop. Head tracking is now a priority
bonus source, replacing its former low-priority treatment. Original care-stat
penalties are discarded; co-op shared loss remains a separate product decision.

## Setup status and open choices

| Question | Working assumption |
| --- | --- |
| Existing board setup? | Some setup is already reported. Inventory exact board/display, pins, firmware and USB behavior; reuse completed work and identify gaps. Details are not yet recorded here. |
| Laptop OS and Python version? | CPython 3.14.6 selected. An HP Windows laptop is the expected deployment host and has programmed/controlled the Pico over USB; initial tooling was also verified on macOS 26.5.2. Keep the code OS-agnostic and avoid fixed device/`COM` paths. |
| Development versus production? | Explicit `dev` and `hardware` profiles compose the same application/rules/codec. Dev uses a clickable virtual Pico, safe temporary storage and protocol trace; hardware uses USB Pico, local SQLite and system clock. Never infer the profile from OS or silently fall back. |
| Sprite style/dimensions and actual redraw speed? | Full pet, small faces, food/animations; size to confirmed LCD and measure. |
| Team size and task assignment? | Four people confirmed; possibly two on software. No assignments in advance; claim individual tasks on the board. |
| Tuning? | Open-ended. Existing values are provisional, not final decisions. Maintain configurable rules and the agreed low-stress behavior. |
| Reward rates, level thresholds and sensor bonus caps? | Sources are agreed; amounts and whether sensor bonuses also affect XP remain open. |
| XP/coin strip placement? | At the top; resolve space alongside clock/small face during the progression milestone. |

The record of user intent belongs here, behavior in MVP goals, APIs in class
design, and wire/storage details in their own specs. Update affected documents
together when a decision changes. Do not require readers to reconcile contradictory
versions or read every technical detail to understand the product.
