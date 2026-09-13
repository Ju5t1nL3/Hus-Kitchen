# Decisions, preferences and open questions

Status: living decision record. Use [todo.md](todo.md) for implementation and
hardware-verification status.

## User preferences to preserve

- Modular, maintainable, easily updated code with independent hackathon ownership.
- Explicit function inputs/outputs and a precise device ↔ laptop contract.
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
- The board is inventoried and working: a TinyCircuits TinyScreen+ with a stacked
  MicroSD/Audio TinyShield, recorded in [tinyscreen/README.md](../tinyscreen/README.md).
  The user selected CPython 3.14.6 for the laptop, with uv/Ruff/Pyright scoped
  to `laptop/`; tuning and reward/XP-strip layout choices remain open.

## Current product decisions

| Decision | Why |
| --- | --- |
| Home: big pet, clock, Feed/Focus buttons | Fits the small display and keeps actions obvious. The clock sits top-centre rather than top-right, because on this hardware the top-right corner is button 2's label slot. |
| Four physical buttons, one per screen corner; configurable bindings and ID-based input | The TinyScreen+ has four built-in corner buttons, so the layout draws each label in its own corner rather than as a bottom strip. Buttons 1–2 keep the meanings designed for the three-button build; buttons 3–4 are the addition: a Down/reverse-cycle action (button 3) and Back (button 4) on setup and settings, and Settings (button 3, a gear icon replacing the earlier hold-button-1 gesture) and Pet (button 4) on Home. Both stay unbound on Feed, where the progression strip owns the bottom-right corner. |
| Break sessions cannot be paused | Break offers only two actions (Again, Home), both of which end the break; keeping a third pause/resume pair added no value once ending was always one press away. |
| Again: skip/end a break and immediately start a new focus session at the last confirmed duration | Lets a user keep working without revisiting Setup, while remaining an explicit press rather than an automatic continuation. |
| Feed opens Food/Drink/Back; Food and Drink cost yarn and are immediately fed | Yarn has an understandable use without adding inventory management. Prices remain open. |
| Individual PNG source frames plus a small ordered animation manifest | Two-frame animations do not justify sprite-sheet slicing; separate files are easier to replace and reduce artwork merge conflicts, while the manifest makes grouping, order and timing explicit. PNGs are converted to firmware bitmap data before deployment. |
| 5–60-minute focus in five-minute steps; default 25, remember last confirmation | Simple adjustable duration. “5s” is interpreted as five-minute increments, as discussed with the user. |
| Break = one-fifth of focus, rounded to whole minutes, minimum one | Transparent proposed product rule; not a universal Pomodoro requirement. |
| Offer a break after completion; do not auto-start | User controls when rest starts; no unattended countdown. |
| Large countdown, small expressive face at top right (Break) | Prioritizes readability; removes progress art from MVP. |
| Focus moves the countdown to the right and adds an animated working-cat mood sprite on the left, instead of a small face | Makes the pet's presence and mood legible during the majority of time spent using the device (an active focus session), not just on Home; Break keeps the original small-face layout since it's brief. |
| Setup's Down cycles one step below the shortest configured duration into a reserved "Debug 10s" entry | Lets developers exercise the full focus/break/completion flow in seconds instead of minutes without adding a hidden dev command or rebuilding firmware; excluded from `allowed_focus_minutes` and from ever becoming the remembered Again/Setup duration so it can't leak into normal use. |
| End and Pause/Resume during focus | Supports accidental starts and interruptions; breaks deliberately cannot pause. |
| Grace below 60 seconds of actual focus; brief sadness after that | Pauses do not consume grace; no lasting punishment. |
| Emotions from saved events and explicit time; catalog pending user specification | Keeps reactions deterministic without hidden numerical stats while allowing the user to choose the final moods/timing. |
| Laptop-only streak/weekly text report | Keeps useful history without cluttering the small device screen. |
| XP raises levels; yarn is spendable currency | Separates progression from Food/Drink purchasing and replaces all product-facing coin terminology. |
| Completed focus earns 3 XP/minute and ceil(minutes/10) yarn; chain position N adds 15% × (N−1) XP (floored) and N−1 yarn, uncapped | Duration-proportional base rewards make every supported timer worthwhile, while a transparent increasing chain bonus encourages “one more” session without punishing a stop. |
| Level thresholds are 75, 100, 125, ... XP with no maximum level | Early levels arrive quickly enough for a demo and first-session reinforcement; linear growth preserves long-term progression without an arbitrary endpoint or explosive grind. |
| Physical Home shows level and yarn, while dev diagnostics may show exact XP | The small production screen stays glanceable and avoids a noisy progress bar; developers retain visibility for balancing and debugging. |
| Keyboard and camera-attention yarn bonuses with separate on/off settings | Both inputs are active planned tasks; base rewards remain available without sensing. |
| Camera model | Use OpenCV's bundled frontal-face Haar cascade for the MVP. Treat a centered frontal face as a coarse attention signal; keep it behind an adapter so a landmark model can replace it later. No frames or identity data are stored. |
| Keyboard gives +1 yarn at 500 presses or +2 at 1,000+, capped at 2 and never grants XP | Optional, gameable activity should feel helpful without overtaking focus completion or disadvantaging reading/thinking; XP remains a clean measure of completed focus. |
| Home button 3 opens persistent opt-in Settings; unavailable host sensors cannot be enabled | Keeps the normal judge flow uncluttered, makes consent explicit, and avoids an apparently enabled feature that does nothing. |
| Level, uninterrupted focus-chain and daily-streak yarn bonuses | Rewards continued work while requiring deduplicated, explainable history facts. |

Existing reaction durations are provisional until M26. Neutral break ending
remains agreed. Exact screen/control behavior is owned by
[product goals](features_and_goals.md).

## Architecture decisions retained or revised

| Decision | Consequence |
| --- | --- |
| Device is a TinyCircuits TinyScreen+ running C++/Arduino, not a Pico running MicroPython | The Pico prototype's external SPI LCD never worked reliably: pin mapping, SPI mode, baud rate, driver choice and power were each ruled out, leaving an intermittent physical connection that could not be fixed remotely. The TinyScreen+ integrates display and four buttons on one board, removing that failure mode entirely, at the cost of a smaller 96x64 screen and a different firmware language. The wire protocol, game rules and laptop architecture were unchanged by the swap, which is the portability rule paying off. |
| Firmware ported rather than rewritten | The MicroPython `protocol.py`/`buttons.py`/`display.py` structure translated directly into C++ classes with the same responsibilities and boundaries, so the firmware contract in class design still holds. |
| Laptop owns rules; the device draws/reports physical gestures | Firmware has no timer, mood or feeding decisions. |
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
never verified, and the Pico + 128x160 ST7735S LCD build that was attempted is now
superseded by the TinyScreen+ and its built-in 96x64 OLED. MicroPython is no
longer the firmware runtime. A future web listener belongs on the laptop. Head
tracking is now a priority bonus source, replacing its former low-priority
treatment. Original care-stat penalties are discarded; co-op shared loss remains
a separate product decision.

## Setup status and open choices

| Question | Working assumption |
| --- | --- |
| Existing board setup? | Resolved. The device is a TinyCircuits TinyScreen+ (ATSAMD21G18A, built-in 96x64 OLED, four corner buttons, USB CDC `0x03EB`/`0x8009`) with a MicroSD/Audio TinyShield stacked on it. The full inventory is in [tinyscreen/README.md](../tinyscreen/README.md). |
| Sound hardware? | Present and working: an audio DAC on pin `A0` via the stacked shield plays procedural cues and an embedded PCM clip. The shield's microSD slot has no card, so file-based audio is not yet possible. Sound stays outside MVP acceptance. |
| Laptop OS and Python version? | CPython 3.14.6 selected. An HP Windows laptop is the expected deployment host and builds, flashes and controls the device over USB; initial tooling was also verified on macOS 26.5.2. Keep the code OS-agnostic and avoid fixed device/`COM` paths. |
| Development versus production? | Explicit `dev` and `hardware` profiles compose the same application/rules/codec. Dev uses a clickable virtual device, safe temporary storage and protocol trace; hardware uses the USB-connected TinyScreen+, local SQLite and system clock. Never infer the profile from OS or silently fall back. |
| Sprite style/dimensions and actual redraw speed? | Full pet, small faces, food/animations; size to confirmed LCD and measure. |
| Team size and task assignment? | Four people confirmed; possibly two on software. No assignments in advance; claim individual tasks on the board. |
| Tuning? | Open-ended. Existing values are provisional, not final decisions. Maintain configurable rules and the agreed low-stress behavior. |
| Final item-price tuning? | Jollof Rice is 3 yarn and Coffee is 2 for now. Both share three-frame Eat, then two-frame Happy for 15 seconds. Starting yarn is 10. |
| Final mood catalog? | User will provide all moods, triggers, precedence and durations before M26. |
| Sensor/daily-streak/level-up bonus rates and caps? | M27 base and focus-chain rates are fixed above; later bonus values remain open. |
| Daily-streak reset/eligibility rules? | Focus-chain boundaries are fixed in progression design; daily timezone and qualification still require a decision before M10/M30. |
| XP/yarn strip placement? | Home-only top strip showing level and yarn in production; exact XP is dev-only. Styling remains adjustable. |

The record of user intent belongs here, behavior in MVP goals, APIs in class
design, and wire/storage details in their own specs. Update affected documents
together when a decision changes. Do not require readers to reconcile contradictory
versions or read every technical detail to understand the product.
