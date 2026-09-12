# Shared contract fixtures

These runtime-neutral JSON Lines files are the agreed examples for laptop and Pico
tests. Each non-empty line is one complete JSON object. Test code must read the
files as data; neither runtime may import code from the other.

| File | Direction/purpose |
| --- | --- |
| `pico_to_laptop.v2.jsonl` | Valid `ready`, `button` and `pong` messages received by the laptop |
| `laptop_to_pico.v2.jsonl` | Valid `hello`, `ping`, complete `render` and `animate` messages received by the Pico |
| `events.v2.jsonl` | Stored event-schema examples, including the active-time early-end boundary |

Fixtures use protocol version 2, UI vocabulary `emotions_v1`, and event schema 2.
They are examples rather than a complete validation schema. The canonical rules and
bounds remain in [`../docs/serial_protocol.md`](../docs/serial_protocol.md) and
[`../docs/event_model.md`](../docs/event_model.md).

When a wire or event contract changes, update its owning document and these files
together. Run the laptop contract tests; the firmware implementation must reuse the
same files or copies verified byte-for-byte by its test setup.

The `ready` fixture advertises button 3. The three-physical-button MVP binds all
three IDs on most screens; Home and the break-running screen use only two and
render the third as a disabled dash, proving that button handling iterates
advertised IDs instead of assuming a fixed count is bound everywhere.
