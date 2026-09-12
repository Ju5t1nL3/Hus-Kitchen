# Post-MVP plan and ordered future ideas

The next milestone is **an XP bar and coin total at the top of the screen**.
Each completed focus session grants XP and coins; crossing a level grants bonus
coins. Keyboard activity and head tracking will add optional coin bonuses.
See [progression_design.md](progression_design.md) for the reward flow and decisions
that still need numerical values. This milestone follows the existing MVP.

## Future ideas — priority order

This is the user-selected order. Keyboard and head tracking come first because
they supply the new completion bonuses. Do not reorder it for implementation convenience.

| Priority | Idea | Goal and implementation boundary |
| --- | --- | --- |
| 1 | Add Keyboard | Pet watches keyboard/mouse activity, cheers/dances/mimics busy work, and taps the screen when idle during focus. Aggregate typing supplies a coin bonus. Independent on/off setting; never store typed text. |
| 2 | Head tracking via laptop webcam | Estimate whether the user remains oriented toward work and award a focus coin bonus. Independent on/off setting; optional emotion reaction to looking away. No numerical care-stat penalties. Process frames locally without saving them. |
| 3 | Sound | Button feedback, user-specific sounds/tags, and possibly alarms. Optional Pico audio driver plays laptop-requested cues. |
| 4 | Weekly dashboard | Show daily, weekly and focus-session recaps on the laptop. Reuse event/report queries; the text recap is already MVP. |
| 5 | GitHub Integration | Commits or merged PRs trigger Coin Rain and XP. Laptop adapter validates/deduplicates activity and calls the reward feature. Use the actual display driver; the original idea called it OLED. |
| 6 | Lightweight Flask/FastAPI server or webhooks | Add a listener when an integration needs it. With the current Pico architecture it runs on the laptop; a server “on the Pi” would require a different board/runtime. |
| 7 | Co-Op Boss Battles | Friends form a party and damage a weekly boss through completed Pomodoros. Shared loot/loss is an original idea requiring a separate product decision; identity, sync, trust and conflict handling need their own design. |
| 8 | Pixel Art Progress Bar | Future timer visualization: pet eats a sandwich, crosses a bridge or builds a wall in step with the timer. This is a future idea, not a deferred former MVP requirement. |
| 9 | The Tab Devourer | A browser extension reports distracting-site visits, then optionally closes/eats tabs or rewards closed tabs. Start with reporting; tab closing and overlays need explicit user controls. |
| 10 | User-specific pets | NFC tags select profiles for scores, pets, clothing, food and sounds. Separate profile state; NFC possession is not authentication. |

The XP bar tracks advancement toward the next level. The pixel-art timer idea at
#8 tracks a session's elapsed time. They are separate features; do not add the
timer visualization to the next XP/coin milestone.

## Extension rules

Use adapters for keyboard/camera/GitHub inputs, pure feature functions for reward
decisions, and Pico rendering for visual/audio output. Every integration uses the
same durable-event path. Adding more food types remains possible through food
definitions; it does not create a new priority item or require an MVP food menu.

The roadmap contains no care-stat system. Expressions remain the pet's feedback.
Do not add unused feature stubs, sensing permissions, or reward fields to MVP code
before their milestone.
