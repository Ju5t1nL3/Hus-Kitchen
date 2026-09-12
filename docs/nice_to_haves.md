# Future features and extension boundaries

This backlog does not expand the current small-screen MVP. The present product is
one food, focus/break timers, pause/resume and event-driven expressions.

## Deferred from the earlier MVP

| Idea | Extension point | Keep out of the current implementation |
| --- | --- | --- |
| More foods | Add food definitions and assets; design selection only when needed | Premium pricing, inventory and a food menu |
| Coins, shop and decorations | New economy/inventory feature with explicit events | Wallet fields, purchase rules and accessory protocol fields |
| Health/hunger/friendship | Reconsider whether numeric care adds value | Hidden stats, decay and stat bars |
| Tricks | New action and animation with a clear button interaction | Extra home/menu controls |
| Pixel-art timer progress | Laptop chooses stage; firmware draws it if space permits | Required progress stages beside the dominant countdown |
| Long breaks and automatic cycles | Extend timer policy and screen flow | Automatic next sessions |
| Resume after restarting the app | Explicit persisted timing/recovery policy | Inferring focus from time the app was closed |

## Original future ideas

| Idea | Intended boundary / first step |
| --- | --- |
| Keyboard/mouse reactions | Opt-in laptop adapter sends aggregate idle/busy events; never raw keystrokes. Feed the emotion rules. |
| Sound/alarms | Optional audio driver; laptop requests cues, with mute and nonblocking playback. |
| Graphical weekly dashboard | Reuse the laptop history queries; text recap remains MVP. |
| Webcam head tracking | Deferred for privacy/CV complexity. Do not add look-away punishment by default. |
| GitHub commits/PRs | Laptop integration validates/deduplicates activity and records an event for a happy reaction. Coin rain/XP would require a separately added economy. |
| Flask/FastAPI listener | Only when an integration needs HTTP; run it on the laptop, not Pico. |
| Co-op boss battles | Separate opt-in sync/projection layer. Stable IDs help but do not solve trust, ordering or conflicts. Reconsider collective punishment. |
| Tab Devourer | Start with opt-in domain/category visit reports from a browser extension. Tab closing and overlays are separate expansions. |
| NFC and user-specific pets | Explicit identity/profile selection plus assets; NFC possession is not authentication. |

## Adding a feature

Keep external inputs in adapters, decisions in feature modules, and drawing in
firmware. Add typed events and replay rules when durable behavior changes. Extend
the wire format only if the screen/device needs new information, coordinating
both ends and examples. Do not create placeholder frameworks for these ideas.
