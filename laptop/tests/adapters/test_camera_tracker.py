"""Tests for camera classification that do not open a real webcam."""

import unittest

from deskpet.adapters.camera_tracker import has_centered_face


class CameraTrackerTests(unittest.TestCase):
    def test_centered_frontal_face_is_attentive(self) -> None:
        faces = ((40, 30, 20, 20),)
        self.assertTrue(has_centered_face(faces, 100, 80, 0.2))

    def test_off_center_or_missing_face_is_not_attentive(self) -> None:
        off_center = ((0, 0, 10, 10),)
        self.assertFalse(has_centered_face(off_center, 100, 80, 0.2))
        self.assertFalse(has_centered_face((), 100, 80, 0.2))


if __name__ == "__main__":
    unittest.main()
