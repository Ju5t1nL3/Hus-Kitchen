"""Tests for the privacy-minimal pynput adapter lifecycle."""

import unittest
from collections.abc import Callable
from unittest.mock import patch

from deskpet.adapters.keyboard_tracker import PynputKeyboardTracker


class ListenerStub:
    def __init__(self, on_press: Callable[[object], None], *, trusted: bool) -> None:
        self.on_press = on_press
        self._is_trusted = False
        self._trusted_after_ready = trusted
        self.started = False
        self.stopped = False
        self.waited = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def wait(self) -> None:
        self.waited = True
        self._is_trusted = self._trusted_after_ready

    @property
    def IS_TRUSTED(self) -> bool:
        return self._is_trusted


class ModuleStub:
    def __init__(self, *, trusted: bool = True) -> None:
        self.trusted = trusted
        self.listener: ListenerStub | None = None

    def Listener(self, *, on_press: Callable[[object], None]) -> ListenerStub:
        self.listener = ListenerStub(on_press, trusted=self.trusted)
        return self.listener


class KeyboardTrackerTests(unittest.TestCase):
    def test_counts_only_while_active_and_never_retains_key_objects(self) -> None:
        module = ModuleStub()
        tracker = PynputKeyboardTracker()
        with patch(
            "deskpet.adapters.keyboard_tracker.import_module", return_value=module
        ):
            self.assertTrue(tracker.begin(True))
        assert module.listener is not None
        self.assertTrue(module.listener.waited)
        key_object = object()
        module.listener.on_press(key_object)
        tracker.pause()
        module.listener.on_press(key_object)
        tracker.resume()
        module.listener.on_press(key_object)

        summary = tracker.finish()

        self.assertEqual(summary.keypress_count, 2)
        self.assertTrue(summary.available)
        self.assertFalse(hasattr(tracker, "keys"))
        tracker.stop()
        self.assertTrue(module.listener.stopped)

    def test_missing_permission_reports_unavailable_without_counting(self) -> None:
        module = ModuleStub(trusted=False)
        tracker = PynputKeyboardTracker()
        with patch(
            "deskpet.adapters.keyboard_tracker.import_module", return_value=module
        ):
            self.assertFalse(tracker.begin(True))

        self.assertFalse(tracker.finish().available)
        assert module.listener is not None
        self.assertTrue(module.listener.stopped)


if __name__ == "__main__":
    unittest.main()
