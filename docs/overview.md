# Desk pet: the simple explanation

Read this first to understand the plan. The other documents provide details for
whoever implements each part. This is a proposed design; the code is not built yet.

## What are we building?

A little desk pet with a screen and buttons, connected to your laptop by USB.
It shows a clock, helps you do Pomodoros, and earns coins when you finish one.
You can feed it, make it do a trick, and buy a small decoration. It also keeps
your daily streak and a weekly activity summary. The pet never dies.

## What runs where?

The laptop makes the decisions: timer, coins, food, mood, purchases and history.
The Pico handles the physical device: reading buttons and drawing the screen.

For example, the Pico reports “button 2 was pressed.” The laptop knows that the
food menu is open, checks whether you can afford the food, saves the purchase,
and tells the Pico what to display next.

The USB messages carry these meanings:

| Direction | What gets sent |
| --- | --- |
| Pico → laptop | “I'm ready,” “this button was pressed/held,” and replies to connection checks |
| Laptop → Pico | Connection setup/checks, a complete description of the screen, and animation requests |

The actual messages are small JSON objects. You only need the
[exact message specification](serial_protocol.md) when implementing USB communication.

## How do we split the code?

There are four main jobs. These can be assigned to different teammates:

| Job | Responsibility | Example |
| --- | --- | --- |
| Game rules | Decide what actions do | Finishing focus earns coins; buying food spends them |
| Saving and history | Remember what happened and produce summaries | Restore the pet after restarting the app |
| Pico and artwork | Buttons, screen, sprites and animations | Draw the hungry pose the laptop selected |
| App and communication | Connect the other parts and manage the current screen | Turn a button press into the selected menu action |

They agree on what information each function receives and returns before building
separately. One integration owner handles shared definitions and configuration.
That reduces teammates editing the same files, though it cannot eliminate every
merge conflict. The [team plan](hackathon_plan.md) maps these jobs to files.

## What happens when a Pomodoro finishes?

1. The laptop notices that its timer has finished.
2. It saves “session completed” together with the earned reward.
3. It updates the pet's coins and streak.
4. It tells the Pico to show completion and play a celebration.
5. After a brief celebration, it tells the Pico to show the clock again.

Saving first means a restart can recover the reward without granting it twice.

Think of the saved history as a receipt book and the current pet stats as the
balance calculated from those receipts. SQLite is simply the local database file
that holds them. The currently selected menu is temporary and need not be saved.

## Why does this make updates easier?

Changing food prices belongs in configuration. Changing feeding behavior belongs
in the game rules. Changing the pet's appearance belongs in Pico artwork.
Replacing the screen mainly affects its hardware driver.

A future GitHub integration can tell the laptop about a commit and reuse the
existing saving/reward/animation flow. We don't need to build that integration now.

## What should we build first?

Make one button start a short focus session, show its timer, and save one reward
when it finishes. Then add feeding, the shop, history and the remaining artwork.
Use a simulated device while hardware is being prepared.

You can stop reading here for the big picture. For the next level of detail, use
[MVP behavior](features_and_goals.md) or the [team plan](hackathon_plan.md).
The class, event and protocol documents are implementation references; nobody
needs to memorize them all. The full document index is in [AGENTS.md](../AGENTS.md).
