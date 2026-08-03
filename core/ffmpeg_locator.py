"""Tìm các chương trình FFmpeg khi chạy source hoặc bản PyInstaller."""

from __future__ import annotations

import os
import shutil
import sys


def get_app_root() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _find_executable(name: str) -> str | None:
    executable = f"{name}.exe" if os.name == "nt" else name
    app_root = get_app_root()
    bundle_root = getattr(sys, "_MEIPASS", None)
    candidates = (
        os.path.join(bundle_root, "bin", executable) if bundle_root else None,
        os.path.join(app_root, "bin", executable),
        os.path.join(app_root, executable),
        shutil.which(name),
    )
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return None


def find_ffmpeg() -> str:
    path = _find_executable("ffmpeg")
    if not path:
        raise FileNotFoundError(
            "Không tìm thấy FFmpeg. Hãy đặt ffmpeg.exe trong thư mục bin "
            "cạnh ứng dụng hoặc thêm FFmpeg vào PATH hệ thống."
        )
    return path


def find_ffprobe() -> str | None:
    return _find_executable("ffprobe")
