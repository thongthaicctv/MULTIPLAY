import os
import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

from core.ffmpeg_locator import find_ffmpeg, find_ffprobe


class FFmpegLocatorTests(unittest.TestCase):
    def test_finds_bundled_ffmpeg_in_bin(self):
        with tempfile.TemporaryDirectory() as folder:
            executable = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
            path = Path(folder, "bin", executable)
            path.parent.mkdir()
            path.touch()
            with patch("core.ffmpeg_locator.get_app_root", return_value=folder), patch(
                "core.ffmpeg_locator.shutil.which", return_value=None
            ):
                self.assertTrue(os.path.samefile(find_ffmpeg(), path))

    def test_raises_clear_error_when_ffmpeg_is_missing(self):
        with tempfile.TemporaryDirectory() as folder, patch(
            "core.ffmpeg_locator.get_app_root", return_value=folder
        ), patch("core.ffmpeg_locator.shutil.which", return_value=None):
            with self.assertRaisesRegex(FileNotFoundError, "Không tìm thấy FFmpeg"):
                find_ffmpeg()

    def test_ffprobe_is_optional(self):
        with tempfile.TemporaryDirectory() as folder, patch(
            "core.ffmpeg_locator.get_app_root", return_value=folder
        ), patch("core.ffmpeg_locator.shutil.which", return_value=None):
            self.assertIsNone(find_ffprobe())

    def test_finds_ffmpeg_inside_pyinstaller_bundle(self):
        with tempfile.TemporaryDirectory() as folder:
            executable = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
            path = Path(folder, "bin", executable)
            path.parent.mkdir()
            path.touch()
            with patch.object(sys, "_MEIPASS", folder, create=True), patch(
                "core.ffmpeg_locator.get_app_root", return_value="X:/app"
            ), patch("core.ffmpeg_locator.shutil.which", return_value=None):
                self.assertTrue(os.path.samefile(find_ffmpeg(), path))


if __name__ == "__main__":
    unittest.main()
