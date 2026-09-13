"""UTC and monotonic clock adapter with conservative resume detection."""

import time
from datetime import UTC, datetime

from deskpet.core.models import ClockReading

_LONG_GAP_MS = 5_000


class SystemClock:
    """Read paired clocks and flag long or inconsistent application gaps."""

    def __init__(self) -> None:
        self._previous: ClockReading | None = None

    def read(self) -> ClockReading:
        utc = datetime.now(UTC)
        monotonic_ms = time.monotonic_ns() // 1_000_000
        previous = self._previous
        resumed = False
        if previous is not None:
            mono_delta = monotonic_ms - previous.monotonic_ms
            utc_delta = int((utc - previous.utc).total_seconds() * 1_000)
            resumed = (
                mono_delta < 0
                or mono_delta > _LONG_GAP_MS
                or abs(utc_delta - mono_delta) > _LONG_GAP_MS
            )
        reading = ClockReading(utc, monotonic_ms, resumed)
        self._previous = reading
        return reading
