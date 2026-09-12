# Product goals and MVP

Tracks: Game & Gamification; Work and Productivity.

Build a gamified productivity companion that stays on the desk, connects to a
laptop, and makes checking a phone less tempting. The user also wants code that is
modular, maintainable, easy to update, and divisible among hackathon teammates.

Status: original feature intent preserved, with proposed scope limits and defaults
made explicit. Numerical tuning belongs in configuration at implementation time;
values here are proposals, not measured product decisions.

## MVP scope

| Feature | Required behavior | Smallest useful scope |
| --- | --- | --- |
| Pet + clock | Large pet and laptop-provided local clock in idle view | One pet with happy, sad, sick and focused poses |
| Focus timer | Start, show countdown, complete, or cancel a Pomodoro | Configured duration, initially 25 minutes; no pause/break scheduler |
| Pet care | Fullness, friendship and health influence appearance | Stats 0–100, recoverable neglect, basic feeding and one trick |
| Coins + purchases | Completed focus earns coins; buy food and decoration | Free basic food, one premium food, one purchasable/equippable accessory |
| Controls | Physical buttons select actions through laptop logic | Two-button baseline; optional third-button shortcut |
| Focus progress | Legible numerical timer plus pixel-art progression | Nine stages (0–8) of one metaphor, e.g. sandwich eating |
| History | Durable activity history, daily streak and weekly totals | SQLite events and laptop CLI/text recap; dashboard deferred |
| Resilience | Restart reconstructs state; USB reconnect restores screen | Clear disconnected view; no lost or duplicate completion rewards |

Decorating and buying food are included, but a large shop, arbitrary task tracker,
multiple pets, XP system, and graphical laptop dashboard are not MVP. Coins come
from completed Pomodoros initially; productivity integrations come later.

## Interaction defaults

The laptop maps gestures to commands. Firmware sends physical gestures only.
Short press is emitted on release; a hold emits once after its threshold and
suppresses the release press. This prevents a hold from also buying food.

| Context | Button 1 PRESS | Button 2 PRESS | Either button HOLD |
| --- | --- | --- | --- |
| Clock | Open menu at `start_focus` | Open menu at `stats` | No action |
| Menu | Cycle through entries | Activate selected entry | Return to clock |
| Pomodoro | No action | No action | Cancel session and return to clock |

If present, button 3 PRESS returns from menu to clock and does nothing elsewhere;
button 3 HOLD cancels focus. Mappings are laptop configuration. A `stats` menu
entry displays the three stats and streak; activating it returns to clock.

Menu order: `start_focus`, `stats`, `feed_basic`, `feed_premium`, `trick`,
`buy_accessory`, `toggle_accessory`, `back`. The laptop supplies the selected
entry's enabled flag and cost. Disabled actions show feedback without changing
durable state. Only `stats` reveals stat bars/numbers. Firmware chooses layouts
from supplied view fields, not inferred game conditions.

## Pet and session rules

- `hunger` is retained as the stat name but means fullness: 100 = well fed,
  0 = hungry. Use a clear “Fullness” label in the UI.
- Stats stay within 0–100 and coins never become negative. Free basic food must
  restore enough fullness/health to avoid a zero-coin recovery dead end.
- Time-based decay happens only while the application is awake and running.
  No catch-up penalty after closing the app or suspending the laptop.
- Explicit focus cancellation may show a temporary sad pose; it does not remove
  coins or impose lasting stat damage. Restart/suspend recovery is neutral.
- Completing a session awards its configured coins and friendship once and
  earns one qualifying day for streak purposes. Briefly display zero seconds and
  the final progress stage during celebration (proposed two seconds), then return
  to clock. A hold can dismiss that completed view without cancelling anything.
- USB disconnect alone does not cancel focus; the laptop continues to run.
  Application restart or detected system sleep cancels active focus without
  rewards. Resumable sessions are deferred.
- Appearance priority: sick, then temporary sad feedback, then focused, then
  hunger-related sad, then happy. Sick remains visible during focus.

## Acceptance criteria

1. Boot the Pico and laptop: the clock/pet appears without manual state setup.
2. Start a short configured demo session: a legible timer and progressing pixel
   art appear; stats remain hidden.
3. Complete it: coins increase exactly once, a celebration plays, and the clock
   returns. Restart cannot replay the celebration or grant another reward.
4. Feed, perform a trick, purchase/equip an accessory, and inspect stats using
   two buttons. Unaffordable or repeated purchases cannot create negative coins.
5. Cancel focus or neglect the pet: it remains recoverable; zero coins cannot
   permanently prevent care.
6. Restart with the same database: pet, coins, purchases and history reconstruct.
   A text report shows weekly completions, focus minutes and streak.
7. Unplug/replug USB: the full current view is restored; stale input is discarded.
8. Exercise core rules using a fake clock/device without connected hardware.

Measure responsiveness on hardware. Target under 50 ms from a recognized
debounced gesture to the start of the resulting screen update; record gesture
recognition and full LCD refresh separately. A hard 50 ms bound from initial
physical contact is not assumed before driver and hardware tests.
