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

## Current product decisions

| Decision | Why |
| --- | --- |
| Home: big pet, top-right clock, Feed/Focus buttons | Fits the small display and keeps actions obvious. |
| Two physical buttons with screen-specific labels | No touchscreen or third button dependency. |
| One free food with a separate definition and sprite | Small MVP with room for more foods later. |
| 5–60-minute focus in five-minute steps; default 25, remember last confirmation | Simple adjustable duration. “5s” is interpreted as five-minute increments, as discussed with the user. |
| Break = one-fifth of focus, rounded to whole minutes, minimum one | Transparent proposed product rule; not a universal Pomodoro requirement. |
| Offer a break after completion; do not auto-start | User controls when rest starts; no unattended countdown. |
| Large countdown, small expressive face at top right | Prioritizes readability; removes progress art from MVP. |
| End and Pause/Resume during focus and break | Supports accidental starts and interruptions. |
| Grace below 60 seconds of actual focus; brief sadness after that | Pauses do not consume grace; no lasting punishment. |
| Emotions from saved events and explicit time | Predictable content/happy/sad reactions without hidden numerical stats. |
| Laptop-only streak/weekly text report | Keeps useful history without cluttering the Pico. |

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

Health/hunger/friendship, coins, a shop, premium food, accessories, tricks and
pixel-art timer progress are outside the current MVP, including background
mechanics. The old fixed-duration/no-pause focus flow is also superseded.
The [backlog](nice_to_haves.md) retains future ideas without keeping them as
active requirements. References to those concepts elsewhere should clearly be
historical or deferred.

Original hardware notes alternated Pico/Pi Zero and LCD/OLED; those choices were
not verified. The plan assumes Pico with the listed LCD behind a replaceable driver.
A future web listener belongs on the laptop. Original webcam/co-op punishment
ideas still need product reconsideration before implementation.

## Open choices

| Question | Working assumption |
| --- | --- |
| Exact board, display, pins and USB ownership? | Pico + 1.8-inch LCD + two buttons; confirm before wiring. |
| Laptop OS and Python version? | Team selects and verifies serial and system-sleep behavior. |
| Sprite style/dimensions and actual redraw speed? | Full pet, small faces, food/animations; size to confirmed LCD and measure. |
| Team members? | Four ownership areas; combine them if the team is smaller. |
| Tuning? | Values in MVP goals/config proposal; maintain neutral breaks and brief reactions. |

The record of user intent belongs here, behavior in MVP goals, APIs in class
design, and wire/storage details in their own specs. Update affected documents
together when a decision changes. Do not require readers to reconcile contradictory
versions or read every technical detail to understand the product.
