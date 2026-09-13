# Expanded milestone and ordered future ideas

XP, levels, spendable yarn, purchasable Food/Drink, keyboard counts, camera
attention and streak/level bonuses have been promoted into the active task board
before final verification. See [progression_design.md](progression_design.md).

## Future ideas — priority order

This preserves the user-selected idea order. Rows 1 and 2 are now active M28/M29
work rather than uncommitted future scope. Do not reorder the remaining ideas for
implementation convenience.

| Priority | Idea | Goal and implementation boundary |
| --- | --- | --- |
| 1 | Add Keyboard *(promoted to M28)* | Count keyboard activity during active focus and award optional yarn. Independent on/off setting; never store keys or typed text. Pet reactions and mouse behavior remain later choices. |
| 2 | Camera attention *(promoted to M29)* | Estimate locally observed attention during active focus and award optional yarn. Independent on/off setting; never save frames/video or perform identity/face recognition. |
| 3 | Sound | Button feedback, user-specific sounds/tags, and possibly alarms. The stacked MicroSD/Audio TinyShield puts a real DAC on pin A0, and firmware already plays short procedural tones locally; what remains is having the laptop request cues over the protocol. Recorded audio needs a microSD card, which is not currently fitted, so file playback is still unavailable. |
| 4 | Weekly dashboard | Show daily, weekly and focus-session recaps on the laptop. Reuse event/report queries; the text recap is already MVP. |
| 5 | GitHub Integration | Commits or merged PRs trigger Yarn Rain and XP. Laptop adapter validates/deduplicates activity and calls the reward feature. Use the actual display driver; the board's panel is an OLED, matching the original idea. |
| 6 | Lightweight Flask/FastAPI server or webhooks | Add a listener when an integration needs it. With the current split it runs on the laptop; a server “on the device” would require a different board/runtime. |
| 7 | Co-Op Boss Battles | Friends form a party and damage a weekly boss through completed Pomodoros. Shared loot/loss is an original idea requiring a separate product decision; identity, sync, trust and conflict handling need their own design. |
| 8 | Pixel Art Progress Bar | Future timer visualization: pet eats a sandwich, crosses a bridge or builds a wall in step with the timer. This is a future idea, not a deferred former MVP requirement. |
| 9 | The Tab Devourer | A browser extension reports distracting-site visits, then optionally closes/eats tabs or rewards closed tabs. Start with reporting; tab closing and overlays need explicit user controls. |
| 10 | User-specific pets | NFC tags select profiles for scores, pets, clothing, food and sounds. Separate profile state; NFC possession is not authentication. |
| 11 | Idle-triggered sleep | If a minute passes with no button press while on Home, show the Sleeping mood regardless of the activity-derived mood; any button press wakes the pet and immediately reveals its true current state (whatever mood/screen would otherwise apply). This is presentation-only (a runtime idle timer and a presenter override, not a new event or durable state) but needs a decision on where that idle clock lives and how it interacts with the existing mood-precedence rules before implementation. |

The XP bar tracks advancement toward the next level. The pixel-art timer idea at
#8 tracks a session's elapsed time. They are separate features.

## Extension rules

Use adapters for keyboard/camera/GitHub inputs, pure feature functions for reward
decisions, and firmware rendering for visual/audio output. Every integration uses the
same durable-event path. Adding more food types remains possible through food
definitions; it does not create a new priority item or require an MVP food menu.

The roadmap contains no care-stat system. Expressions remain the pet's feedback.
Implement active sensing only in its claimed task; do not add unused stubs early.
