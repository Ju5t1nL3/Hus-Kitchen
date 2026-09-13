"""Cross-platform, privacy-minimal global keypress counter."""

import threading
from collections.abc import Callable
from importlib import import_module
from typing import Protocol, cast

from deskpet.core.models import KeyboardSummary


class _Listener(Protocol):
    @property
    def IS_TRUSTED(self) -> bool: ...

    def start(self) -> None: ...

    def wait(self) -> None: ...

    def stop(self) -> None: ...


class _KeyboardModule(Protocol):
    Listener: Callable[..., _Listener]


class PynputKeyboardTracker:
    """Count press callbacks only; key objects are intentionally discarded."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._listener: _Listener | None = None
        self._count = 0
        self._capturing = False
        self._available = True

    def begin(self, enabled: bool) -> bool:
        with self._lock:
            self._count = 0
            self._capturing = False
            self._available = True
        if not enabled:
            return True
        try:
            self._ensure_listener()
        except Exception:
            with self._lock:
                self._available = False
            return False
        with self._lock:
            self._capturing = True
        return True

    def pause(self) -> None:
        with self._lock:
            self._capturing = False

    def resume(self) -> None:
        with self._lock:
            if self._available and self._listener is not None:
                self._capturing = True

    def finish(self) -> KeyboardSummary:
        with self._lock:
            self._capturing = False
            return KeyboardSummary(self._count, self._available)

    def stop(self) -> None:
        with self._lock:
            listener = self._listener
            self._listener = None
            self._capturing = False
        if listener is not None:
            listener.stop()

    def _ensure_listener(self) -> None:
        with self._lock:
            if self._listener is not None:
                return
        module = cast(_KeyboardModule, cast(object, import_module("pynput.keyboard")))
        listener = module.Listener(on_press=self._on_press)
        listener.start()
        listener.wait()
        if not listener.IS_TRUSTED:
            listener.stop()
            raise RuntimeError("keyboard monitoring permission is unavailable")
        with self._lock:
            self._listener = listener

    def _on_press(self, _key: object) -> None:
        with self._lock:
            if self._capturing:
                self._count += 1
