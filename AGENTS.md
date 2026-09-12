# Tamagotchi Desk Pet

A gamified productivity companion: a physical desk pet (small LCD + buttons on a
Raspberry Pi Pico) tethered via USB to a laptop, which runs the actual game logic.
Goal: replace phone-checking with a glanceable, low-friction desk device that reacts
to real productivity signals (Pomodoros, GitHub activity, idle time).

## Architecture

Two runtimes, one serial link between them:

- **Laptop (Python)** — the "brain." Owns all game logic, state, and persistence.
  Nothing about hunger decay, streaks, or coin rewards should ever live on the Pico.
- **Pico (MicroPython)** — a dumb peripheral. Renders whatever state it's told to
  render and reports button presses. It does not compute or reason about anything.

This split is deliberate and should not be violated: if a feature needs "logic,"
it goes in the laptop script; the Pico only ever displays numbers/sprites it's given
and forwards raw button events.

## Serial Protocol

Plain-text, line-delimited (`\n`-terminated), read via `readline()` on both ends.

**Laptop → Pico** (render commands):
```
STATE <happy|sad|sick|sleeping|focused>
HUNGER <0-100>
FRIENDSHIP <0-100>
HEALTH <0-100>
TIMER <seconds_remaining>
COINS <int>
ANIM <feed|coin_rain|trick|wake_up>
MODE <clock|pomodoro|menu>
SLEEP
PING
```

**Pico → Laptop** (input events):
```
READY          # sent once on boot
BTN <n> PRESS
BTN <n> HOLD
PONG
```

Rules:
- Pico ignores unknown commands (forward-compatible).
- Pico debounces buttons itself — only clean press/hold events are sent.
- Laptop must read serial on a background thread (not inside the slower game-tick
  loop), so button presses aren't delayed up to a full tick interval. Target: <50ms
  round-trip from physical press to Pico re-render.

## Data Model

Two separate concerns — do not merge them:

- **`events.json` (or SQLite)** — append-only log of everything that happened
  (`pomodoro_complete`, `github_commit`, `blacklist_site_visited`, `pet_fed`, ...).
  This is the durable source of truth. Streaks, weekly recaps, and co-op boss damage
  are all just queries over this log.
- **`game_state`** — the current-value cache (hunger, coins, friendship, streak)
  derived from the event log, updated incrementally as new events arrive. This is
  what gets pushed to the Pico each tick. It should be fully reconstructable by
  replaying `events.json` from scratch if it ever gets corrupted or a new stat is added.

## UI Rules

- **Idle mode**: pet is large/central, stats (hunger/friendship/health numbers) are
  hidden by default — classic Tamagotchi feel. Pet's pose/color implicitly signals
  mood (droopy if hungry, bright if happy) without needing numbers. Numbers/bars are
  shown only on an explicit button press.
- **Pomodoro mode**: timer must be legibly sized (not tiny) since it's the
  functionally important value in that mode. Pet is smaller/centered showing a
  "focused" pose. No stat bars shown — avoid inviting mid-session decisions.
  Progress is shown via a pixel-art visual metaphor (e.g. pet eating a sandwich /
  building a bridge) instead of a plain bar.
- Sick/distressed pose is the one exception that should always be visible, even
  mid-Pomodoro — it's ambient, not a number, so it doesn't break focus.

## Feature Priority (roughly ranked)

1. Core loop: idle/pomodoro states, hunger/friendship/health, button-driven mode switch.
2. Event log + derived streaks/weekly recap.
3. GitHub webhook integration (commit/PR → coin rain + XP) — reuses the same
   event-log → animation-trigger pathway as Pomodoro completion, so build it next.
4. Context-aware reactions (keyboard/mouse activity → pet response).
5. Co-op boss battles — requires a sync layer; design the event log to be
   sync-able (append-only, user/device-tagged) if this is planned, rather than
   retrofitting multiplayer later.
6. Tab Devourer browser extension — start with the extension just *reporting*
   blacklisted-site visits into the event log (pet reacts sadly), rather than the
   harder version where it actively closes tabs.

Explicitly deprioritized for v1: webcam head tracking (privacy/CV complexity not
worth it for the payoff).

## Design Principles to Preserve

- **No punishing failure states.** Missing a Pomodoro or neglecting the pet should
  make it sad/sick, never "die" — the goal is reducing stress, not adding guilt.
- **Local-first / privacy-first.** No data leaves the laptop unless a feature
  explicitly requires it (e.g. co-op sync). Worth stating this as a selling point.
- **Config-driven rules.** Blacklisted sites, coin values, and thresholds belong in
  `config.yaml`, not hardcoded, since these will need tuning.
- **C++/Pico SDK is not needed.** MicroPython is sufficient for this project's
  timing requirements (no real-time audio, no high-frame-rate graphics). Don't
  reach for the C toolchain unless display refresh or audio timing genuinely demands it.

## Repo Layout (planned)

```
tamagotchi-desk-pet/
├── main.py                 # laptop entry point
├── serial_link.py           # threaded serial read/write to Pico
├── game_state.py             # current stats, derived from event log
├── pomodoro.py                 # timer logic
├── event_log.py                  # append-only log read/write
├── github_webhook.py               # Flask/FastAPI listener
├── activity_monitor.py               # keyboard/mouse idle detection
├── weekly_report.py                    # recap generation from event log
├── config.yaml                           # user-editable rules/thresholds
├── data/                                   # events.json or pet.db
└── pico/
    ├── main.py                                # boot + main loop
    ├── display.py                               # LCD driver wrapper
    ├── sprites.py                                 # pixel art frames
    └── buttons.py                                   # debounced GPIO reads
```
