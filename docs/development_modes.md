# Development and hardware modes

The laptop application supports two runtime profiles built from the same game
rules, coordinator, protocol codec and screen presenter. A profile selects external
resources and diagnostics; it must never change timer, feeding, emotion or reward
behavior.

| Profile | Device | Storage | Clock | Diagnostics |
| --- | --- | --- | --- | --- |
| `dev` | Clickable virtual Pico | Temporary/in-memory by default; explicit path allowed | Real by default; controllable fake clock available | Visible bidirectional wire trace and validation errors |
| `hardware` | USB-connected Pico | User's local SQLite database | System UTC + monotonic clock | Normal structured logs; no development UI |

Use `hardware` as this local product's production profile. The expected demo host
is Windows, while profile selection and application logic remain OS-agnostic.
Choose the profile explicitly through the eventual CLI/configuration. Do not infer
it from the operating system, silently fall back to the simulator when USB fails,
or let development mode write the normal user database by default.

## Clickable virtual Pico

Development mode opens a small local UI representing the physical setup:

- Pico/USB connection indicator and connect, disconnect and reboot controls.
- LCD-sized screen preview using the current render snapshot.
- One clickable control for every button ID advertised by the simulated device;
  the MVP defaults to IDs 1, 2 and 3.
- One normal clickable press per button, with its current label and enabled state.
- Optional fake-clock controls to advance a long focus or break quickly.
- A chronological trace with direction, timestamp, raw JSON line, decoded message
  type and accepted/rejected reason.
- Clear, pause, copy/export and invalid-message injection controls for debugging.

The drawing is a functional virtual breadboard, not an electrical authority. GPIO
wiring and voltage facts remain in the Pico hardware documentation. Once the real
layout is known, the UI may arrange the Pico, display and buttons similarly, but it
must label the view as simulated.

## Exercise the real boundary

A click must not call a feeding or timer function directly. It creates the same
Pico-to-laptop JSON button message as firmware, passes through the production wire
decoder and enters the normal application input queue. Laptop renders and animation
cues pass through the production encoder before the virtual Pico validates and
displays them.

The simulator uses an in-memory byte transport so it does not need a serial port.
It may host its UI in a local browser or desktop window; keep that choice inside the
development adapter. A browser server must bind to loopback only and stop with the
application. It is a development interface, not the future network integration.

Trace entries are diagnostics, not gameplay events, and must never enter event
replay or weekly reports. Bound the trace in memory and redact future secrets or
sensitive sensor data before display/export.

## Inputs and outputs

| Component/API | Input | Output |
| --- | --- | --- |
| `build_application(profile, config_path, data_path)` | Explicit profile, validated config path and optional storage path | One application composed with matching adapters |
| `SimulatorPort.push_from_device(data)` | One bounded JSON byte line | Bytes delivered to the production laptop decoder |
| `SimulatorPort.write(data)` | Bytes from the real laptop serial link | Bytes validated and applied by the virtual Pico |
| `VirtualPico.press(button, gesture)` | Advertised button ID and normal press | Versioned button JSON with connection, boot, sequence and control epoch |
| `VirtualPico.accept_host_bytes(data)` | Laptop hello/ping/render/animate bytes | Updated connection/screen/animation state or traced rejection |
| `TraceSink.record(...)` | Direction, raw line, message type and result | Bounded ordered diagnostic entry |

## Completion checks

Run one complete focus path through the simulator: connect, open setup, cycle and
confirm a duration, pause, advance time, resume, complete, then start or skip the
break. Confirm that both trace directions show the same compact JSON Lines used by
the shared fixtures. Disconnect/reconnect, stale epoch and malformed/oversized-line
scenarios must use the real codec behavior. Run the same application tests under
both profiles where hardware can be replaced by an in-memory transport.

## Current commands

From `laptop/`, run `uv run python main.py --profile dev`, then open the printed
`127.0.0.1` URL. This uses a temporary SQLite database unless `--data PATH` is
provided. `--simulator-port PORT` changes only the loopback UI port. Run hardware
explicitly with `uv run python main.py --profile hardware`; neither profile falls
back to the other.
