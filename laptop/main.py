"""Explicit development and hardware composition root for the laptop app."""

import argparse
from enum import StrEnum
from pathlib import Path

from deskpet.adapters.config_loader import load
from deskpet.adapters.keyboard_tracker import PynputKeyboardTracker
from deskpet.adapters.serial_device_link import SerialDeviceLink
from deskpet.adapters.serial_discovery import (
    PortableDeviceResolver,
    PySerialBackend,
    PySerialEnumerator,
)
from deskpet.adapters.simulator import (
    ControllableClock,
    SimulatorBackend,
    SimulatorDeviceLink,
    TraceSink,
    VirtualPico,
)
from deskpet.adapters.simulator_web import SimulatorWebServer
from deskpet.adapters.sqlite_event_store import SqliteEventStore
from deskpet.adapters.system_clock import SystemClock
from deskpet.adapters.temporary_event_store import TemporaryEventStore
from deskpet.app.application import Application
from deskpet.core.ports import (
    DeviceAmbiguous,
    DeviceNotFound,
    DeviceSelector,
)

ROOT = Path(__file__).resolve().parent


class RuntimeProfile(StrEnum):
    DEV = "dev"
    HARDWARE = "hardware"


def build_application(
    profile: RuntimeProfile,
    config_path: Path,
    data_path: Path | None = None,
    *,
    simulator_port: int = 8765,
) -> Application:
    """Compose explicit dev or hardware resources around one application."""
    config = load(config_path)
    if profile is RuntimeProfile.DEV:
        clock = ControllableClock()
        trace = TraceSink()
        pico = VirtualPico(clock, trace)
        backend = SimulatorBackend(pico)
        # Manual timer jumps must not impersonate heartbeat timeouts.
        serial_link = SerialDeviceLink(backend, SystemClock())
        device = SimulatorDeviceLink(serial_link, backend, pico, clock, trace)
        device.attach_server(SimulatorWebServer(device, simulator_port))
        store = (
            TemporaryEventStore() if data_path is None else SqliteEventStore(data_path)
        )
        return Application(
            store,
            device,
            clock,
            config,
            keyboard_tracker=PynputKeyboardTracker(),
        )

    selector = DeviceSelector(
        port=config.device.port,
        vendor_id=config.device.usb_vid,
        product_id=config.device.usb_pid,
        serial_number=config.device.serial_number,
    )
    result = PortableDeviceResolver().resolve(selector, PySerialEnumerator().list())
    if isinstance(result, DeviceNotFound):
        raise RuntimeError("no serial device matches the configured Pico selector")
    if isinstance(result, DeviceAmbiguous):
        ports = ", ".join(candidate.port for candidate in result.candidates)
        raise RuntimeError(f"multiple serial devices match; configure one: {ports}")
    clock = SystemClock()
    device = SerialDeviceLink(PySerialBackend(result.candidate.port), SystemClock())
    store = SqliteEventStore(data_path or ROOT / "data" / "pet.db")
    return Application(
        store,
        device,
        clock,
        config,
        keyboard_tracker=PynputKeyboardTracker(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Tamagotchi desk pet")
    parser.add_argument(
        "--profile",
        type=RuntimeProfile,
        choices=tuple(RuntimeProfile),
        required=True,
        help="explicit runtime profile; dev never falls back to hardware or vice versa",
    )
    parser.add_argument("--config", type=Path, default=ROOT / "config.yaml")
    parser.add_argument(
        "--data",
        type=Path,
        help="SQLite path; dev uses temporary storage when omitted",
    )
    parser.add_argument(
        "--simulator-port",
        type=int,
        default=8765,
        help="loopback HTTP port used only by the dev profile",
    )
    args = parser.parse_args()
    application = build_application(
        args.profile,
        args.config,
        args.data,
        simulator_port=args.simulator_port,
    )
    try:
        application.start()
        application.run()
    except KeyboardInterrupt:
        pass
    finally:
        application.stop()


if __name__ == "__main__":
    main()
