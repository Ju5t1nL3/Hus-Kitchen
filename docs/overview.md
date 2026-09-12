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

There are no health bars, hidden hunger meters, coins or shop in this MVP.
It never dies. Daily streaks and a weekly text summary use the same saved diary
and stay on the laptop.

## How do we divide the work?

| Teammate's area | Builds |
| --- | --- |
| Game rules | Timer transitions, feeding and emotion selection |
| Saving and history | Local database, restart recovery and summaries |
| Pico and artwork | Buttons, display, pet/face/food sprites and animations |
| App and communication | Screen controls and the USB connection between everything |

Agree on the shared messages and function inputs/outputs first, then work in
separate files. One integration owner coordinates shared definitions. Details are
in the [team plan](hackathon_plan.md).

## What should we build first?

Make the home/setup/timer screens work, then connect one complete focus session
to a saved completion and a break offer. Add pause/end behavior, feeding and
emotions, and test with the real device. A simulated device lets laptop work begin
before the hardware is ready.

Food definitions, emotion rules and sprite drawing are separate, so adding another
food or changing the artwork later does not require rewriting the timer.

For exact behavior, read [MVP goals](features_and_goals.md). The full document map
is in [AGENTS.md](../AGENTS.md); you do not need to read every specification at once.
