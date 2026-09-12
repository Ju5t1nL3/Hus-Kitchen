# Desk pet: the simple explanation

This is the current plan, not built code. Start here; the other docs are references
for implementing specific parts.

## What does it do?

When you first plug it in, you see a big pet, a clock at the top right, and two
button labels: **Feed** and **Focus**.

Feed gives it one kind of food and plays a cute animation. Focus opens a screen
where the left button cycles through 5, 10, 15 … 60 minutes and back to 5.
The right button confirms. The first selection is 25 minutes; later it remembers
your last confirmed choice.

The countdown fills most of the screen, with a small pet face at the top right.
The buttons become **End** and **Pause/Resume**. Pausing freezes the timer.

Ending before one minute of actual focus is treated as an accidental start.
Ending later still works, but the pet looks sad briefly. Time spent paused does
not count toward that minute.

When focus finishes, the pet celebrates and offers a break. The break is one-fifth
of the focus time: 25 minutes of focus gives 5 minutes of rest. You choose whether
to start it. Finishing or ending the break takes you home without a penalty.

## What runs where?

| Part | Job |
| --- | --- |
| Laptop | Timer, pause/resume, break calculation, emotions and saved history |
| Pico | Read physical buttons and draw the screen the laptop requests |

The Pico says “button 1 was pressed.” The laptop knows whether that means Feed,
Up, End or Home on the current screen. The laptop then sends the updated screen
description. The Pico never decides that a session is complete or that the pet
should be sad.

## How does the pet feel?

The laptop keeps a diary of feeding and focus events. A recent feeding makes it
content; a completed focus makes it happy; ending focus after the grace period
makes it briefly sad. The latest applicable reaction wins and fades after a short
time. Otherwise the pet looks calm, focused or resting according to what you do.

Health, hunger and friendship are removed entirely, including hidden meters.
Coins and XP arrive immediately after this MVP.
It never dies. Daily streaks and a weekly text summary use the same saved diary
and stay on the laptop.

## How do we pick up work?

| Software area | Includes |
| --- | --- |
| Game rules | Timer transitions, feeding and emotion selection |
| Saving and history | Local database, restart recovery and summaries |
| Pico and artwork | Buttons, display, pet/face/food sprites and animations |
| App and communication | Screen controls and the USB connection between everything |

There are four people on the team, but possibly only two working on software.
These are parts of the code, not assigned roles. Pick any available task in
[todo.md](todo.md), add your GitHub handle, mark it Doing, and check it off when
verified. Coordinate shared files with other task claimants; the
[team plan](hackathon_plan.md) explains integration.

## What should we build first?

Make the home/setup/timer screens work, then connect one complete focus session
to a saved completion and a break offer. Add pause/end behavior, feeding and
emotions, and test with the real device. A simulated device lets laptop work begin
before the hardware is ready.

Food definitions, emotion rules and sprite drawing are separate, so adding another
food or changing the artwork later does not require rewriting the timer.

Button assignments also live in one mapping. To move an existing action to another
button, change that mapping; its label follows automatically. New hardware buttons
reuse the scanner and USB messages rather than needing new game logic.

## What comes next?

First add an XP bar and coin total at the top. Finishing focus earns XP and coins;
gaining a level gives extra coins. Next, keyboard activity and webcam head tracking
can earn coin bonuses. You can turn either sensor on or off independently.
Reward amounts and level thresholds still need to be chosen.

The future-feature order starts keyboard, head tracking, sound, then a weekly
dashboard. Pixel-art timer progress is later, at #8; it is not the XP bar.
See the [ordered roadmap](nice_to_haves.md) and [reward plan](progression_design.md).

## What should I review to agree on the plan?

Read [MVP goals](features_and_goals.md) for current behavior, then the
[roadmap](nice_to_haves.md) for priority order and [progression design](progression_design.md)
for rewards, toggles and undecided amounts. [Design decisions](design_decisions.md)
separates decisions/defaults from open questions. For button flexibility, read
“Adding or changing buttons” in [class design](class_design.md).

For exact behavior, read [MVP goals](features_and_goals.md). The full document map
is in [AGENTS.md](../AGENTS.md); you do not need to read every specification at once.
