"""Đọc metadata video bằng ffprobe."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass

from core.ffmpeg_locator import find_ffprobe


@dataclass(frozen=True)
class VideoInfo:
    width: int = 0
    height: int = 0
    duration: float | None = None
    codec: str = ""
    has_audio: bool = False


def probe_video(path: str, logger: logging.Logger | None = None) -> VideoInfo:
    ffprobe = find_ffprobe()
    if not ffprobe:
        if logger:
            logger.warning("Không tìm thấy ffprobe; dùng metadata mặc định cho %s", path)
        return VideoInfo()

    command = [
        ffprobe,
        "-v", "error",
        "-show_streams",
        "-show_format",
        "-of", "json",
        path,
    ]
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=True,
            creationflags=creationflags,
        )
        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        video = next((s for s in streams if s.get("codec_type") == "video"), {})
        duration_value = video.get("duration") or data.get("format", {}).get("duration")
        duration = float(duration_value) if duration_value not in (None, "N/A") else None
        return VideoInfo(
            width=int(video.get("width") or 0),
            height=int(video.get("height") or 0),
            duration=duration,
            codec=str(video.get("codec_name") or ""),
            has_audio=any(s.get("codec_type") == "audio" for s in streams),
        )
    except (OSError, ValueError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        if logger:
            logger.warning("Không đọc được metadata của %s: %s", path, exc)
        return VideoInfo()
