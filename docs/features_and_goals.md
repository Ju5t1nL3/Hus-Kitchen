# Product goals and MVP

Build a small, expressive desk pet that helps you focus without checking your
phone. Keep the code modular, maintainable and easy to divide among teammates.
This is the current small-screen design; it replaces the earlier stats/shop MVP.
Use [todo.md](todo.md) for implementation and hardware-verification status.

## Screens and three-button controls

Three physical buttons sit below the screen, left to right as button 1/2/3. Draw
their current labels above them. They are not touchscreen buttons. The third
button acts as a back/cancel button on most screens, but not on every screen: on
Home and the running/paused break screen it has no back destination and takes on
a different role instead (unbound on Home and break-running; "Time" during
focus). Unbound buttons show a disabled dash, per the button-labeling rule in
[class design](class_design.md).

| Screen | What is visible | Button 1 | Button 2 | Button 3 |
| --- | --- | --- | --- | --- |
| Home | Large central pet; clock plus compact level/yarn strip (exact XP is dev-only) | Feed: open menu | Focus: open setup | *(unbound)* |
| Feed menu | Current yarn balance; Food and Drink with their configured yarn prices | Buy/feed Food | Buy/feed Drink | Back: cancel to Home |
| Setup | Selected focus minutes; smaller calculated break duration | Up: next duration | Set: start focus | Back: cancel to Home |
| Focus, running | Large central countdown; small expressive face at top right | Time: show the real clock | Pause | End |
| Focus, paused | Frozen countdown; “Paused”; small face at top right | Time: show the real clock | Resume | End |
| Focus complete (break offer) | Happy pet; “Focus complete”; proposed break minutes | Break: start the break | Again: skip the break and start a new focus session immediately, using the previous duration | Home: skip the break and return to Home |
| Break, running | Large countdown; “Break”; small face at top right | Again: end the break and start a new focus session immediately, using the previous duration | Home: end the break and return to Home | *(unbound)* |

Breaks can no longer be paused; ending one always goes either straight into
another focus session (Again) or back to Home. Holds do nothing in MVP; firmware
emits one press OR one hold per gesture, never both. Labels should fit the actual
screen; the state machine and actions stay on the laptop.

**Time reveal.** Pressing Time on a running or paused focus screen swaps the
countdown for the actual wall-clock time (e.g. "4:00", the same HH:MM format used
on Home) for five seconds, then automatically reverts to the countdown. This is
a temporary render toggle, not a durable event, and does not pause the timer or
change the control epoch.

**Again (repeat the last focus duration).** From the break offer or a running
break, Again ends/skips the break and starts a brand-new focus session at the
previously confirmed duration, without visiting Setup. It reuses the existing
start-focus and skip/end-break rules; no new event type is needed.

These are default bindings, not hardcoded branches throughout the app. Changing
an existing action's button updates the controls configuration. Labels and input
handling use the same action definitions; the [class design](class_design.md)
explains how to add a physical button or new behavior.

## Duration and break rules

- The selector is in **minutes**: 5 → 10 → … → 60 → 5. First use starts at 25;
  later uses start at the last confirmed duration. Just cycling does not save it.
- The laptop computes the break before confirmation. Proposed product rule:
  `break_minutes = max(1, floor(focus_minutes / 5 + 0.5))`. Every allowed MVP
  duration divides exactly by five: 5→1, 25→5, 60→12.
- This is our proportional break rule, not a claim that Pomodoro requires it.
  Keep allowed durations, defaults and break ratio in laptop configuration.
- Completing focus records completion once, plays a brief celebration and opens
  the break offer. A break begins only when the user presses Break.
- Ending focus early returns home with no break offer. Ending a break returns
  either to Home or straight into a new focus session, both by explicit button
  press (Home or Again). There is no automatic next focus session or long-break
  cycle; Again is a manual shortcut that skips Setup, not an automatic
  continuation.
- Pause freezes remaining time and contributes no focused time, and only applies
  to focus; breaks cannot be paused. Resume continues from that remaining time.
  Pausing, or ending/skipping a break by any path, has no penalty.

## Early ending and emotions

End always works immediately, including while paused. Use actual accumulated
focus time, excluding pauses: below 60 seconds is an accidental-start grace exit;
at exactly 60 seconds or later, an early exit produces brief sadness. Completion
wins if the timer is already due when an End/Pause input is handled.

The pet reacts to recorded events, with no hidden hunger, health or friendship
meters. The table below describes the currently implemented provisional catalog;
M26 will replace or confirm it after the user supplies every desired mood, trigger,
precedence rule and duration:

| Event or situation | Appearance |
| --- | --- |
| Feed | Content for 20 seconds; play feeding animation |
| Focus completes | Static Party scene on the break offer; M27 supplies earned XP/yarn text |
| User ends unfinished focus after grace | Sad until five runtime-only Pet taps; at restart the tap count resets |
| Grace exit, pause, break skip/end, system interruption | No new sadness |
| No unexpired reaction, focus running | Focused |
| No unexpired reaction, break running | Resting |
| Otherwise | Calm |

The latest unexpired feed/completion/early-end reaction wins, ordered by event
sequence. Once the newest reaction expires, use the current activity's default
above; do not revive an older reaction. The small
face during a timer can therefore show an emotion too. No accumulating punishment,
death, offline neglect, or permanent damage. See [event_model.md](event_model.md)
for how reactions are stored and replayed.

End currently navigates straight to Home, where the sad reaction above is already
visible on the pet. **Nice to have:** instead of going straight to Home, briefly
show a dedicated full-screen sad interstitial for 5 seconds, then automatically
continue to Home. This is a presentation-only addition (a new Screen value and a
runtime auto-advance timer, same shape as the focus-screen clock reveal); it
changes no rule, event, or emotion duration and is not required for MVP.

## Progression, feeding and assets

XP increases toward progressively harder, uncapped levels and cannot be spent.
Yarn is the spendable currency. Completed focus grants the approved duration and
focus-chain XP/yarn breakdown from progression design; later tasks add optional
keystroke/camera yarn plus level-up and daily-streak yarn bonuses. Those later
bonus rates remain open; M27's base/chain rates and level curve are fixed.

Home's Feed action opens the Feed menu. Food and Drink each display a configured
yarn price. Choosing an affordable item atomically spends yarn, feeds the pet and
records the resolved price/reaction; insufficient yarn changes nothing. Back
returns Home without an event. The current direction is immediate purchase and
feeding, with no inventory, quantities, cooldown or shop browsing.

Feed is available while Idle, Happy, or Hungry. Sad disables Feed until five Pet
taps clear Sad. Any successful feeding resets the five-minute hunger deadline.

The configured catalog is Jollof Rice for 3 yarn and Coffee for 2 yarn. Both use
the same three-frame eating animation and then leave the pet Happy for 15 seconds.
Prices, reaction duration and manifest IDs are configuration rather than rule code.

Define consumable data separately from feeding logic. Required assets now include
Food and Drink sprites/feeding frames plus the mood and celebration art. Artwork
production remains coordinated with M16. Source frames are individual PNGs grouped
by an ordered manifest and converted to Pico bitmap data before deployment.

## History and recovery

Keep a local event time series for feeding and session start/pause/resume/end/
completion. Daily streaks and a weekly text recap remain laptop-only; no report
menu or stat bars on the Pico. Completed focus earns a streak day; an early-ended
session is logged separately and never counts as completed.

USB reconnect restores the current screen while the laptop keeps running. App
restart or detected system sleep ends any unfinished focus/break neutrally; manual
pause/resume is supported for focus (breaks cannot pause), but resume across app
restarts is deferred. A saved pending break offer survives restart. A fresh
installation starts on Home.

## Product boundary and next milestone

Health/hunger/friendship are permanently removed, including hidden values and
decay; they are not a deferred feature. Feeding and expressions remain.

The approved pre-verification expansion is XP, levels, yarn and purchasable
Food/Drink, followed by the user-defined mood catalog, base rewards, optional
keyboard/camera yarn, then level/focus-chain/daily-streak bonuses and weekly recap.
See [progression design](progression_design.md). Pixel-art timer progress remains a
later idea separate from the XP bar.

## Acceptance checks

1. Home shows a large pet, clock, readable XP/level/yarn information and Feed/Focus
   labels on the real LCD, with a disabled dash on the unbound third button.
2. Feed opens Food/Drink/Back; an affordable choice spends its displayed yarn cost
   and feeds once, while Back and insufficient funds make no durable change.
3. Setup cycles 5–60 minutes, wraps, shows the derived break and confirms
   correctly; Back returns to Home without starting a session or an event.
4. Pause/resume preserves remaining time for focus; paused time cannot consume
   the grace period. Break has no Pause/Resume buttons at all.
5. End at 59.999 focused seconds is neutral; End at 60 seconds is briefly sad.
6. Completion is saved once; the break starts only when Break is pressed. Ending
   a break via Home, or skipping/ending it via Again, is neutral, and break
   minutes never count as focus.
7. Again, from the break offer or a running break, starts a new focus session at
   the previously confirmed duration without visiting Setup, and does not create
   a break-completion or extra event beyond the normal skip/end and start events.
8. Time, pressed during a running or paused focus session, shows the real clock
   for 5 seconds and then automatically reverts to the countdown, without
   changing the timer, pausing it, or bumping the control epoch.
9. The user-approved mood catalog triggers and expires exactly as specified; no
   permanent negative state or care meter exists.
10. Restart/reconnect preserves history without duplicate completions or replayed
    animations. Pending breaks and interrupted sessions follow the policy above.
11. Completed focus grants one deduplicated XP/yarn breakdown; optional sensor and
    streak/level bonuses remain explainable, additive and independently testable.
12. Test rules using a fake device/clock, then measure actual LCD/button behavior.

Target under 50 ms from a recognized debounced gesture to the start of its screen
update. Measure gesture recognition and full redraw separately; hardware performance
has not been verified. Accelerate the fake clock for tests instead of changing the
production selector to seconds.
