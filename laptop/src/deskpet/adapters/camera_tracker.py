"""Local, cross-platform camera attention tracker using OpenCV."""

import threading
import time
from collections.abc import Sequence
from pathlib import Path

import cv2
from cv2.typing import Rect

from deskpet.core.models import AttentionStatus, AttentionSummary


class OpenCvHaarAttentionTracker:
    """Classify centered frontal-face samples; never retain or publish frames."""

    def __init__(
        self,
        *,
        camera_index: int = 0,
        sample_interval_seconds: float = 0.5,
        away_seconds: float = 5.0,
        center_margin_ratio: float = 0.2,
    ) -> None:
        if sample_interval_seconds <= 0 or away_seconds <= 0:
            raise ValueError("camera intervals must be positive")
        if not 0 <= center_margin_ratio < 0.5:
            raise ValueError("center_margin_ratio must be in [0, 0.5)")
        self._camera_index = camera_index
        self._sample_interval = sample_interval_seconds
        self._away_seconds = away_seconds
        self._center_margin = center_margin_ratio
        self._lock = threading.Lock()
        self._capture: cv2.VideoCapture | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._capturing = False
        self._available = True
        self._attempted = 0
        self._observed = 0
        self._attentive = 0
        self._away_since: float | None = None

    def begin(self, enabled: bool) -> bool:
        self.stop()
        with self._lock:
            self._available = True
            self._attempted = self._observed = self._attentive = 0
            self._away_since = None
        if not enabled:
            return True
        capture = cv2.VideoCapture(self._camera_index)
        if not capture.isOpened():
            capture.release()
            with self._lock:
                self._available = False
            return False
        module_path = cv2.__file__
        cascade_path = (
            Path(module_path).parent / "data" / "haarcascade_frontalface_default.xml"
        )
        cascade = cv2.CascadeClassifier(str(cascade_path))
        if cascade.empty():
            capture.release()
            with self._lock:
                self._available = False
            return False
        with self._lock:
            self._capture = capture
            self._capturing = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._sample_loop,
            args=(cascade,),
            name="camera-attention",
            daemon=True,
        )
        self._thread.start()
        return True

    def pause(self) -> None:
        with self._lock:
            self._capturing = False
            self._away_since = None

    def resume(self) -> None:
        with self._lock:
            if self._available and self._capture is not None:
                self._capturing = True

    def status(self) -> AttentionStatus:
        with self._lock:
            lost = (
                self._capturing
                and self._away_since is not None
                and time.monotonic() - self._away_since >= self._away_seconds
            )
            return AttentionStatus(self._available, lost)

    def finish(self) -> AttentionSummary:
        with self._lock:
            self._capturing = False
            self._away_since = None
            return AttentionSummary(
                self._attempted,
                self._observed if self._available else 0,
                self._attentive if self._available else 0,
                self._available,
            )

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2)
        with self._lock:
            capture = self._capture
            self._capture = None
            self._capturing = False
            self._away_since = None
        if capture is not None:
            capture.release()

    def _sample_loop(self, cascade: cv2.CascadeClassifier) -> None:
        while not self._stop_event.wait(self._sample_interval):
            with self._lock:
                active = self._capturing
                capture = self._capture
            if not active or capture is None:
                continue
            ok, frame = capture.read()
            now = time.monotonic()
            with self._lock:
                if not self._capturing:
                    continue
                self._attempted += 1
                if not ok:
                    self._away_since = None
                    continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
            height, width = gray.shape[:2]
            attentive = has_centered_face(faces, width, height, self._center_margin)
            with self._lock:
                if not self._capturing:
                    continue
                self._observed += 1
                if attentive:
                    self._attentive += 1
                    self._away_since = None
                elif self._away_since is None:
                    self._away_since = now


def has_centered_face(
    faces: Sequence[Rect], width: int, height: int, margin: float
) -> bool:
    return any(
        width * margin <= x + face_width / 2 <= width * (1 - margin)
        and height * margin <= y + face_height / 2 <= height * (1 - margin)
        for x, y, face_width, face_height in faces
    )
