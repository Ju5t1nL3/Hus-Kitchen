"""Hardware composition root for the laptop desk-pet application."""

import argparse
from pathlib import Path

from deskpet.adapters.config_loader import load
from deskpet.adapters.serial_device_link import SerialDeviceLink
from deskpet.adapters.serial_discovery import (
    PortableDeviceResolver,
    PySerialBackend,
    PySerialEnumerator,
)
from deskpet.adapters.sqlite_event_store import SqliteEventStore
from deskpet.adapters.system_clock import SystemClock
from deskpet.app.application import Application
from deskpet.core.ports import (
    DeviceAmbiguous,
    DeviceNotFound,
    DeviceSelector,
)

ROOT = Path(__file__).resolve().parent


def build_application(config_path: Path, data_path: Path) -> Application:
    """Load configuration and compose production resource adapters."""
    config = load(config_path)
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
    store = SqliteEventStore(data_path)
    return Application(store, device, clock, config)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Tamagotchi desk pet")
    parser.add_argument("--config", type=Path, default=ROOT / "config.yaml")
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "pet.db")
    args = parser.parse_args()
    application = build_application(args.config, args.data)
    try:
        application.start()
        application.run()
    except KeyboardInterrupt:
        pass
    finally:
        application.stop()


if __name__ == "__main__":
    main()
