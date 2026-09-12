# Future features and extension boundaries

This is a backlog, not authorization to expand MVP. Original brainstorm order is
retained below; it conflicts with the old AGENTS priority order. Suggested
post-MVP engineering order is GitHub integration, activity reactions, then optional
UI/sound work. Reconsider that order with the team when MVP works.

| Original idea | Future implementation boundary | Design concern / scoped first step |
| --- | --- | --- |
| 1. Keyboard/mouse reactions | `adapters/activity/` emits aggregate inputs; `features/activity/` decides reactions | Opt-in idle/busy summaries, no raw keystrokes. Gentle reactions during focus. |
| 2. Sound and alarms | Optional firmware `AudioDriver`; laptop issues cues | Capability/version negotiation, mute setting, nonblocking playback. No Pico alarm logic. |
| 3. Weekly dashboard | New laptop UI consumes `ReportService` | Text recap is MVP; graphical daily/week/session views reuse queries. |
| 4. Webcam head tracking | Optional laptop camera adapter | Deferred: privacy, permissions and CV complexity. Original look-away health penalty conflicts with low-stress goals. |
| 5. GitHub commits/PRs → coin rain + XP | Laptop HTTP/polling adapter → productivity feature → durable event | Validate webhooks; deduplicate delivery and logical activity. XP needs a new projection/rule. |
| 6. Flask/FastAPI listener | Laptop adapter when an integration needs HTTP | No server on Pico. No HTTP framework required for MVP; Pi Zero migration is a separate decision. |
| 7. Co-op boss battles | Separate sync adapter and co-op projection | Event IDs/origin tags help, but identity, ordering, deduplication, trust and conflicts still need design. Start with shared progress; reconsider collective loot punishment. |
| 8. Pixel-art progress | Laptop chooses stage; firmware draws stage | Promoted to MVP as nine stages alongside a readable timer. |
| 9. Tab Devourer | Browser extension → local laptop input adapter | Start by reporting configured-site visits, ideally domain/category only. Tab closing, desktop overlays and closed-tab rewards are separate opt-in expansions. |
| 10. NFC/user-specific pets | Optional sensor event; laptop identity/inventory feature | Explicit profile selection and separate per-user projections. NFC possession is not authentication. |

## How to add a feature

1. Decide whether it introduces an input, game rule, report, or output adapter.
2. Add typed commands and versioned events only where needed. External adapters
   submit inputs; they do not mutate game state or directly award coins.
3. Implement deterministic rules and replay inside the owning feature.
4. Extend the presenter/protocol only if the Pico must render something new.
5. Add relevant contract fixtures and update the owning design document.

An append-only log helps prepare for sync but does not make shared currency or
distributed ordering safe automatically. Do not merge remote events into the
local pet projection without a designed conflict/trust policy.
