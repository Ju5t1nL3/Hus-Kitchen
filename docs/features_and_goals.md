# Product goals and MVP

Build a small, expressive desk pet that helps you focus without checking your
phone. Keep the code modular, maintainable and easy to divide among teammates.
This is the current small-screen design; it replaces the earlier stats/shop MVP.
All behavior below is planned, not implemented.

## Screens and two-button controls

The two physical buttons sit below the screen. Draw their current labels above
them: button 1 on the left, button 2 on the right. They are not touchscreen buttons.

| Screen | What is visible | Left press | Right press |
| --- | --- | --- | --- |
| Home | Large central pet; clock at top right | Feed | Focus: open setup |
| Setup | Selected focus minutes; smaller calculated break duration | Up: next duration | Confirm: start focus |
| Focus, running | Large central countdown; small expressive face at top right | End | Pause |
| Focus, paused | Frozen countdown; “Paused”; small face at top right | End | Resume |
| Break offer | Happy pet; “Focus complete”; proposed break minutes | Home: skip break | Start break |
| Break, running | Large countdown; “Break”; small face at top right | End | Pause |
| Break, paused | Frozen countdown; “Break paused”; small face | End | Resume |

A hold on either setup button returns home, without starting a session. Holds on
other screens do nothing in MVP. Firmware emits one press OR one hold per gesture,
never both. No third button is required. Labels should fit the actual screen;
the state machine and actions stay on the laptop.

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
  the break offer. A break begins only when the user presses Start break.
- Ending focus early returns home with no break offer. Completing or ending a
  break returns home. There is no automatic next focus session or long-break cycle.
- Pause freezes remaining time and contributes no focused time. Resume continues
  from that remaining time. Pausing or skipping/ending a break has no penalty.

## Early ending and emotions

End always works immediately, including while paused. Use actual accumulated
focus time, excluding pauses: below 60 seconds is an accidental-start grace exit;
at exactly 60 seconds or later, an early exit produces brief sadness. Completion
wins if the timer is already due when an End/Pause input is handled.

The pet reacts to recorded events, with no hidden hunger, health or friendship
meters. Proposed configurable reaction durations:

| Event or situation | Appearance |
| --- | --- |
| Feed | Content for 20 seconds; play feeding animation |
| Focus completes | Happy for 30 seconds; play celebration |
| User ends unfinished focus after grace | Sad for 30 seconds |
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

## Feeding and assets

Home's Feed action immediately offers one free food, `basic`. No shop, cost,
quantity, cooldown, or food-selection screen in MVP. Every accepted press records
one feeding; animation requests can coalesce under rapid presses. Feeding again
refreshes the content reaction rather than accumulating a hidden stat.

Define food data separately from feeding logic so another food can be added later.
Required sprites: one pet's full-body poses, matching small faces for the six moods,
one food sprite (`food_basic`), a feeding animation, and a celebration.
Artwork production remains implementation work; these docs do not provide assets.

## History and recovery

Keep a local event time series for feeding and session start/pause/resume/end/
completion. Daily streaks and a weekly text recap remain laptop-only; no report
menu or stat bars on the Pico. Completed focus earns a streak day; an early-ended
session is logged separately and never counts as completed.

USB reconnect restores the current screen while the laptop keeps running. App
restart or detected system sleep ends any unfinished focus/break neutrally; manual
pause/resume is supported, but resume across app restarts is deferred. A saved
pending break offer survives restart. A fresh installation starts on Home.

## Product boundary and next milestone

Health/hunger/friendship are permanently removed, including hidden values and
decay; they are not a deferred feature. Feeding and expressions remain.

Immediately after MVP, add a top XP bar and coin total, completion XP/coins and
bonus coins for gaining levels. Optional keyboard and head tracking supply
additional coin bonuses, with independent on/off settings. Rates/thresholds still
need values; see [progression design](progression_design.md).

The ordered [future ideas](nice_to_haves.md) begin keyboard → head tracking → sound
→ weekly dashboard. Pixel-art timer progress belongs only at #8 in that list;
it is separate from the next milestone's XP bar.

## Acceptance checks

1. Home shows a large pet, top-right clock and Feed/Focus labels on the real LCD.
2. Feed displays the food sprite/animation and a content reaction, without costs.
3. Setup cycles 5–60 minutes, wraps, shows the derived break and confirms correctly.
4. Pause/resume preserves remaining time; paused time cannot consume the grace period.
5. End at 59.999 focused seconds is neutral; End at 60 seconds is briefly sad.
6. Completion is saved once; the break starts only on confirmation. Ending or
   skipping it is neutral, and its minutes never count as focus.
7. Emotions expire and can change through later events; no permanent negative state.
8. Restart/reconnect preserves history without duplicate completions or replayed
   animations. Pending breaks and interrupted sessions follow the policy above.
9. Test rules using a fake device/clock, then measure actual LCD/button behavior.

Target under 50 ms from a recognized debounced gesture to the start of its screen
update. Measure gesture recognition and full redraw separately; hardware performance
has not been verified. Accelerate the fake clock for tests instead of changing the
production selector to seconds.
