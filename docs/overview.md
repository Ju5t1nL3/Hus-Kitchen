# Desk pet: the simple explanation

This summarizes both implemented foundations and the newly approved work still on
the task board. Start here; the other docs are task-specific references.

## What does it do?

When you first plug it in, you see a big pet, a clock at the top right, and
labels in two of the four screen corners: **Feed** (top-left) and **Focus**
(top-right). The bottom-left corner is **Pet**, which comforts a sad pet, and the
bottom-right corner shows your level and yarn instead of a button label.

Holding the top-left Home button opens Settings without crowding the normal
screen. Up and Down move between Keyboard and Camera, Select toggles an available
option, and Back returns Home. Both begin Off; Camera says Unavailable when the
laptop cannot open one.

Feed opens Food/Drink/Back. Food and Drink show a yarn price; choosing one spends
yarn and feeds the pet immediately if you can afford it. Focus opens a screen
where **Up** (top-left) and **Down** (bottom-left) step through 5, 10, 15 … 60
minutes and wrap around, **Set** (top-right) confirms, and **Back**
(bottom-right) returns home without starting anything. The first selection is
25 minutes; later it remembers your last confirmed choice.

The countdown fills most of the screen, with a small pet face at the top right.
Each button's job changes with the screen. During focus the buttons are **Time**,
**Pause/Resume** and **End**, and the fourth corner stays empty.
Pausing freezes the timer; Time swaps the countdown for the real clock for five
seconds, then switches back on its own.

Ending before one minute of actual focus is treated as an accidental start.
Ending later still works, but the pet looks sad briefly. Time spent paused does
not count toward that minute.

When focus finishes, the pet celebrates and offers a break: **Break** starts it,
**Again** skips it and jumps straight into another focus session at the same
length you just used, and **Home** skips it and goes home. A running break only
has two buttons, **Again** and **Home** — it can no longer be paused, since
ending it was always one press away anyway. Neither path is a penalty.

## What runs where?

| Part | Job |
| --- | --- |
| Laptop | Timer, pause/resume, break calculation, emotions and saved history |
| Device | Read physical buttons and draw the screen the laptop requests |

The device says “button 1 was pressed.” The laptop knows whether that means Feed,
Up, End or Home on the current screen. The laptop then sends the updated screen
description. The device never decides that a session is complete or that the pet
should be sad.

## How does the pet feel?

The laptop keeps a diary of feeding and focus events. A recent feeding makes it
happy; a completed focus opens the Party break offer; ending focus after the grace period
makes it briefly sad. The latest applicable reaction wins and fades after a short
time and requires five Pet taps. Otherwise it is Idle, Hungry, Working, or Sleeping
according to durable timing and the current screen.

Health, hunger and friendship are removed entirely, including hidden meters. XP
raises levels; yarn is earned and spent on Food/Drink. It never dies. Daily streaks
and a weekly text summary use the same saved diary and stay on the laptop.

## How do we pick up work?

| Software area | Includes |
| --- | --- |
| Game rules | Timer transitions, feeding and emotion selection |
| Saving and history | Local database, restart recovery and summaries |
| Firmware and artwork | Buttons, display, pet/face/food sprites and animations |
| App and communication | Screen controls and the USB connection between everything |

There are four people on the team, but possibly only two working on software.
These are parts of the code, not assigned roles. Pick any available task in
[todo.md](todo.md), add your GitHub handle, mark it Doing, and check it off when
verified. Coordinate shared files with other task claimants; the
[team plan](hackathon_plan.md) explains integration.

## What should we build first?

The base home/setup/timer/recovery slice and simulator now exist. Next follow the
progression/economy, Feed menu, user-defined moods, rewards, optional sensors and
streak/report order in [todo.md](todo.md), then verify with the real device.

Food definitions, emotion rules and sprite drawing are separate, so adding another
food or changing the artwork later does not require rewriting the timer.

Button assignments also live in one mapping. To move an existing action to another
button, change that mapping; its label follows automatically. New hardware buttons
reuse the scanner and USB messages rather than needing new game logic.

## What comes next?

XP, yarn, priced feeding, moods and base/focus-chain rewards are implemented.
Optional keyboard counting now adds at most two yarn to a completed focus and
never XP; it stores counts rather than keys or text. Local camera attention is
next, followed by level-up/daily-streak yarn and weekly recap work.

Keyboard and camera bonuses are now active tasks. The remaining future-feature
order continues with sound and then a weekly dashboard. Pixel-art timer progress
remains at original priority #8; it is not the XP bar.
See the [ordered roadmap](nice_to_haves.md) and [reward plan](progression_design.md).

## What should I review to agree on the plan?

Read [MVP goals](features_and_goals.md) for current behavior, then the
[roadmap](nice_to_haves.md) for priority order and [progression design](progression_design.md)
for rewards, toggles and undecided amounts. [Design decisions](design_decisions.md)
separates decisions/defaults from open questions. For button flexibility, read
“Adding or changing buttons” in [class design](class_design.md).

For exact behavior, read [MVP goals](features_and_goals.md). The full document map
is in [AGENTS.md](../AGENTS.md); you do not need to read every specification at once.
