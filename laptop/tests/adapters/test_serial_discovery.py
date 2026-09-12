"""Portable serial candidate resolution tests."""

import unittest

from deskpet.adapters.serial_discovery import PortableDeviceResolver, candidates_from
from deskpet.core.ports import (
    DeviceAmbiguous,
    DeviceNotFound,
    DeviceResolved,
    DeviceSelector,
    SerialCandidate,
)


def candidate(
    port: str,
    *,
    vendor: int | None = 0x2E8A,
    product: int | None = 0x0005,
    serial: str | None = None,
) -> SerialCandidate:
    return SerialCandidate(port, vendor, product, serial, "MicroPython Board")


class PortableDeviceResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.resolver = PortableDeviceResolver()

    def test_configured_windows_port_is_matched_case_insensitively(self) -> None:
        result = self.resolver.resolve(
            DeviceSelector(port="com6"),
            (candidate("COM6"), candidate("COM7")),
        )

        self.assertEqual(result, DeviceResolved(candidate("COM6")))

    def test_posix_port_and_complete_metadata_can_be_selected(self) -> None:
        pico = candidate("/dev/ttyACM0", serial="pico-a")
        result = self.resolver.resolve(
            DeviceSelector(
                vendor_id=0x2E8A,
                product_id=0x0005,
                serial_number="pico-a",
            ),
            (candidate("/dev/ttyUSB0", vendor=0x1234), pico),
        )

        self.assertEqual(result, DeviceResolved(pico))

    def test_missing_and_ambiguous_results_never_pick_first(self) -> None:
        devices = (candidate("COM7"), candidate("COM6"))

        missing = self.resolver.resolve(DeviceSelector(port="COM9"), devices)
        ambiguous = self.resolver.resolve(
            DeviceSelector(vendor_id=0x2E8A, product_id=0x0005), devices
        )

        self.assertIsInstance(missing, DeviceNotFound)
        self.assertEqual(ambiguous, DeviceAmbiguous(devices))

    def test_no_selector_requires_a_unique_candidate(self) -> None:
        only = candidate("/dev/ttyACM0")

        self.assertEqual(
            self.resolver.resolve(DeviceSelector(), (only,)), DeviceResolved(only)
        )
        self.assertIsInstance(
            self.resolver.resolve(DeviceSelector(), (only, candidate("COM6"))),
            DeviceAmbiguous,
        )

    def test_alternate_enumerator_values_are_sorted_deterministically(self) -> None:
        ordered = candidates_from((candidate("COM9"), candidate("com2")))

        self.assertEqual([item.port for item in ordered], ["com2", "COM9"])


if __name__ == "__main__":
    unittest.main()
