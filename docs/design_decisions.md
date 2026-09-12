# Design decisions, user preferences, and open questions

Status: proposed MVP baseline, prepared 2026-09-12 from the four original Markdown
files. No application code exists yet. No hardware tests or external hardware-spec
verification have been performed.

## User intent to retain across sessions

- Make code modular, easily maintainable, and easily updatable.
- Split hackathon work into independently owned sections to minimize merge conflicts.
- Define system design and class/function contracts, especially Pico → laptop data.
- Account for likely future features without prematurely building them.
- Store goals, findings, decisions and plans in Markdown, with AGENTS as entry point.
- Existing Markdown may be cleaned up. The user explicitly clarified that the old
  AGENTS design is editable and should be improved rather than treated as fixed.

## Decisions and reasons

| Decision | Reason / consequence |
| --- | --- |
| One laptop process, separate Pico firmware | Simple deployment; no services/network needed for MVP. |
| Feature modules inside a small layered application | Pet/focus/shop/report changes stay localized; infrastructure is replaceable. |
| Pure rules/reducers, classes for resources | Small dependencies and tests; avoids an all-purpose pet/controller. |
| One state owner, queued serial input | Avoids shared-state locks while keeping buttons responsive. |
| SQLite append-only domain events | Atomic writes and reward uniqueness; simpler crash handling than rewriting a JSON array. |
| Durable state separate from UI/render state | Menus, connectivity and animation do not pollute history. |
| Store resolved effects and reward terms in events | History does not change when config prices or rewards change. |
| Versioned JSON Lines over USB | Complete snapshots and explicit schemas replace expanding positional text commands. |
| Full snapshots, separate transient cues | Simple reconnect and consistent screen fields. |
| Two-button baseline | Works with minimum listed hardware; third button is optional. |
| Text recap in MVP, dashboard later | Resolves weekly logs appearing in both feature lists. |
| Small shop and progress art in MVP | Preserves purchases/decorations and focus UI goals at limited scope. |
| No offline decay; cancel interrupted focus neutrally | Simple recovery and no guilt for sleep/restarts. Resume can come later. |
| One configured local user/device initially | Stable origin IDs now; NFC and co-op remain separate features. |

## Findings corrected from the original notes

- “Pico / Pi Zero W” was ambiguous; assume Pico pending confirmation.
- LCD versus OLED and exact hardware details remain open; domain code is independent.
- Old render commands lacked clock text, menu content, progress, version handshake,
  and atomic screen updates. The new protocol replaces that proposal; there is
  no implemented legacy protocol to migrate.
- Replay was underspecified for decay/config changes. Initialization, elapsed-time
  effects, pinned rewards, deterministic ordering and replay are now specified.
- Blocking `readline()` on firmware could starve buttons. Assemble bounded lines
  from available bytes instead.
- Serial input wakes the application immediately rather than waiting for a tick.
- Future “server on the Pi” belongs on the laptop for this architecture.
- Original co-op punishment and look-away penalties conflict with low-stress goals.
  Those ideas remain recorded but require a new product decision.

## Assumptions and unresolved choices

These do not block software design/simulation. Resolve hardware before wiring and
tuning before the demo.

| Question | Working assumption | Consequence if changed |
| --- | --- | --- |
| Exact board/display/wiring? | Pico + 1.8-inch LCD + two buttons | Change firmware config/driver; platform change may affect transport. |
| Laptop OS/Python version? | Team chooses one supported development OS | Confirm serial permissions, suspend behavior and dependencies. |
| USB channel/display throughput? | App owns bidirectional stream; redraw supports target | Validate on device and document measured latency. |
| Team size/names? | Four ownership areas, not four required people | Combine areas; preserve shared-file ownership. |
| Coins/decay/care effects/feedback duration? | Tune config; care remains accessible | Events preserve old applied effects; new rules affect new actions. |
| Art/accessory identity? | One pet, one accessory, nine progress stages | Add assets; change schema only if fields/semantics change. |
| Focus/break behavior? | 25-minute focus; no pause/automatic break | Extend focus events and interaction contract if needed. |

## Documentation maintenance

AGENTS is navigation and concise guidance, not a duplicate specification. Product
behavior belongs in features/goals; wire details in serial protocol; signatures in
class design. Record reasons here and update the canonical specifications so
readers see one current answer. Do not leave contradictory alternatives active.
