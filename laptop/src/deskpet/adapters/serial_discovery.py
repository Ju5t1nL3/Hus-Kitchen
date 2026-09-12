"""Portable pyserial discovery, deterministic selection and port opening."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

import serial  # pyright: ignore[reportMissingModuleSource]
from serial.tools import list_ports  # pyright: ignore[reportMissingModuleSource]

from deskpet.core.ports import (
    DeviceAmbiguous,
    DeviceNotFound,
    DeviceResolved,
    DeviceSelector,
    ResolveResult,
    SerialCandidate,
)


class SerialPort(Protocol):
    def readline(self) -> bytes: ...

    def write(self, data: bytes, /) -> int | None: ...

    def close(self) -> None: ...


class SerialBackend(Protocol):
    def open(self) -> SerialPort: ...


class PySerialEnumerator:
    """Enumerate serial metadata without embedding OS-specific port rules."""

    def list(self) -> tuple[SerialCandidate, ...]:
        candidates = (
            SerialCandidate(
                port=item.device,
                vendor_id=item.vid,
                product_id=item.pid,
                serial_number=item.serial_number,
                description=item.description,
            )
            for item in list_ports.comports()
        )
        return tuple(
            sorted(candidates, key=lambda candidate: candidate.port.casefold())
        )


class PortableDeviceResolver:
    """Resolve only exact configured criteria and never guess among matches."""

    def resolve(
        self,
        selector: DeviceSelector,
        candidates: tuple[SerialCandidate, ...],
    ) -> ResolveResult:
        matches = tuple(
            candidate for candidate in candidates if _matches(selector, candidate)
        )
        if not matches:
            return DeviceNotFound(selector)
        if len(matches) > 1:
            return DeviceAmbiguous(matches)
        return DeviceResolved(next(iter(matches)))


@dataclass(frozen=True, slots=True)
class PySerialBackend:
    """Open one already-resolved port with bounded reads for clean shutdown."""

    port: str
    baudrate: int = 115_200
    timeout_seconds: float = 0.05
    write_timeout_seconds: float = 0.25

    def __post_init__(self) -> None:
        if not self.port:
            raise ValueError("port must not be empty")
        if self.baudrate <= 0:
            raise ValueError("baudrate must be positive")
        if self.timeout_seconds <= 0 or self.write_timeout_seconds <= 0:
            raise ValueError("serial timeouts must be positive")

    def open(self) -> SerialPort:
        try:
            return serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout_seconds,
                write_timeout=self.write_timeout_seconds,
            )
        except serial.SerialException as error:
            raise OSError(f"cannot open serial port {self.port}: {error}") from error


def _matches(selector: DeviceSelector, candidate: SerialCandidate) -> bool:
    if (
        selector.port is not None
        and selector.port.casefold() != candidate.port.casefold()
    ):
        return False
    if selector.vendor_id is not None and selector.vendor_id != candidate.vendor_id:
        return False
    if selector.product_id is not None and selector.product_id != candidate.product_id:
        return False
    return not (
        selector.serial_number is not None
        and selector.serial_number != candidate.serial_number
    )


def candidates_from(
    values: Iterable[SerialCandidate],
) -> tuple[SerialCandidate, ...]:
    """Return a deterministic candidate order for alternate enumerator adapters."""
    return tuple(sorted(values, key=lambda candidate: candidate.port.casefold()))
