# Decisions, preferences and open questions

Status: living decision record. Use [todo.md](todo.md) for implementation and
hardware-verification status.

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
- Before final verification, add XP/levels/yarn and purchasable Food/Drink, then
  user-defined moods, base rewards, optional keyboard/camera yarn, and
  level/focus-chain/daily-streak bonuses with weekly recap work.
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
| Feed opens Food/Drink/Back; Food and Drink cost yarn and are immediately fed | Yarn has an understandable use without adding inventory management. Prices remain open. |
| Individual PNG source frames plus a small ordered animation manifest | Two-frame animations do not justify sprite-sheet slicing; separate files are easier to replace and reduce artwork merge conflicts, while the manifest makes grouping, order and timing explicit. PNGs are converted to firmware bitmap data before deployment. |
| 5–60-minute focus in five-minute steps; default 25, remember last confirmation | Simple adjustable duration. “5s” is interpreted as five-minute increments, as discussed with the user. |
| Break = one-fifth of focus, rounded to whole minutes, minimum one | Transparent proposed product rule; not a universal Pomodoro requirement. |
| Offer a break after completion; do not auto-start | User controls when rest starts; no unattended countdown. |
| Large countdown, small expressive face at top right | Prioritizes readability; removes progress art from MVP. |
| End and Pause/Resume during focus | Supports accidental starts and interruptions; breaks deliberately cannot pause. |
| Grace below 60 seconds of actual focus; brief sadness after that | Pauses do not consume grace; no lasting punishment. |
| Emotions from saved events and explicit time; catalog pending user specification | Keeps reactions deterministic without hidden numerical stats while allowing the user to choose the final moods/timing. |
| Laptop-only streak/weekly text report | Keeps useful history without cluttering the Pico. |
| XP raises levels; yarn is spendable currency | Separates progression from Food/Drink purchasing and replaces all product-facing coin terminology. |
| Keyboard and camera-attention yarn bonuses with separate on/off settings | Both inputs are active planned tasks; base rewards remain available without sensing. |
| Level, uninterrupted focus-chain and daily-streak yarn bonuses | Rewards continued work while requiring deduplicated, explainable history facts. |

Existing reaction durations are provisional until M26. Neutral break ending
remains agreed. Exact screen/control behavior is owned by
[product goals](features_and_goals.md).

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

Health/hunger/friendship are removed from the product, not deferred. XP/levels/yarn
are an approved pre-verification expansion specified in
[progression design](progression_design.md).
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
| Food/Drink prices/reactions? | Feed-menu behavior is agreed; values and item-specific reactions/assets remain open. Starting yarn is provisionally 10 in validated config. |
| Final mood catalog? | User will provide all moods, triggers, precedence and durations before M26. |
| Reward rates, level thresholds and sensor/streak bonus caps? | Sources are agreed; amounts and whether non-base bonuses also affect XP remain open. |
| Focus-chain and daily-streak reset/eligibility rules? | Concepts are agreed; exact boundaries/timezone require user decisions before M10/M30. |
| XP/yarn strip placement? | Home-only top strip with level, XP within its threshold, and yarn; styling remains adjustable. |

The record of user intent belongs here, behavior in MVP goals, APIs in class
design, and wire/storage details in their own specs. Update affected documents
together when a decision changes. Do not require readers to reconcile contradictory
versions or read every technical detail to understand the product.
