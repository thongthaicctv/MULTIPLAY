"""Worker ghép đồng thời 2-4 video bằng FFmpeg."""

from __future__ import annotations

import logging
import os
import subprocess
import threading
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from core.ffmpeg_locator import find_ffmpeg, get_app_root
from core.video_probe import VideoInfo, probe_video


SUPPORTED_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".ts"}
VALID_LAYOUTS = {"auto", "horizontal", "vertical", "grid"}


def validate_merge_inputs(input_paths: list[str], output_path: str) -> None:
    if len(input_paths) < 2:
        raise ValueError("Vui lòng chọn ít nhất 2 video để ghép.")
    if len(input_paths) > 4:
        raise ValueError("Phase 2 chỉ hỗ trợ ghép tối đa 4 video.")
    if not output_path:
        raise ValueError("Chưa chọn đường dẫn lưu video kết quả.")

    output_key = os.path.normcase(os.path.abspath(output_path))
    errors: list[str] = []
    for path in input_paths:
        if Path(path).suffix.lower() not in SUPPORTED_EXTENSIONS:
            errors.append(f"Định dạng không hỗ trợ: {path}")
        elif not os.path.isfile(path):
            errors.append(f"Không tồn tại: {path}")
        elif not os.access(path, os.R_OK):
            errors.append(f"Không có quyền đọc: {path}")
        if os.path.normcase(os.path.abspath(path)) == output_key:
            errors.append(f"File kết quả không được trùng file nguồn: {path}")
    if errors:
        raise ValueError("Không thể ghép video:\n" + "\n".join(errors))

    output_dir = os.path.dirname(os.path.abspath(output_path)) or os.curdir
    if not os.path.isdir(output_dir):
        raise ValueError(f"Thư mục đích không tồn tại: {output_dir}")
    if not os.access(output_dir, os.W_OK):
        raise ValueError(f"Không có quyền ghi thư mục đích: {output_dir}")


def resolve_layout(layout: str, count: int) -> str:
    if layout not in VALID_LAYOUTS:
        raise ValueError(f"Bố cục không hợp lệ: {layout}")
    if layout == "auto":
        return "horizontal" if count == 2 else "grid"
    return layout


def build_ffmpeg_command(
    ffmpeg_path: str,
    input_paths: list[str],
    temp_output: str,
    layout: str,
    video_infos: list[VideoInfo],
) -> list[str]:
    count = len(input_paths)
    resolved = resolve_layout(layout, count)
    if resolved == "grid" and count < 2:
        raise ValueError("Bố cục lưới cần ít nhất 2 video.")

    if resolved == "horizontal":
        cell_w = 640 if count == 2 else (480 if count == 3 else 400)
    else:
        cell_w = 640
    cell_h = round(cell_w * 9 / 16)

    filters = []
    for index in range(count):
        filters.append(
            f"[{index}:v]scale={cell_w}:{cell_h}:force_original_aspect_ratio=decrease,"
            f"pad={cell_w}:{cell_h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=25[v{index}]"
        )

    labels = "".join(f"[v{i}]" for i in range(count))
    if resolved == "horizontal":
        filters.append(f"{labels}hstack=inputs={count}[vout]")
    elif resolved == "vertical":
        filters.append(f"{labels}vstack=inputs={count}[vout]")
    else:
        positions = ["0_0", f"{cell_w}_0", f"0_{cell_h}", f"{cell_w}_{cell_h}"]
        filters.append(
            f"{labels}xstack=inputs={count}:layout={'|'.join(positions[:count])}:"
            "fill=black[vgrid]"
        )
        filters.append(
            f"[vgrid]pad={cell_w * 2}:{cell_h * 2}:0:0:black[vout]"
        )

    command = [ffmpeg_path, "-hide_banner", "-y"]
    for path in input_paths:
        command.extend(["-i", path])
    command.extend([
        "-filter_complex", ";".join(filters),
        "-map", "[vout]",
    ])

    audio_index = next((i for i, info in enumerate(video_infos) if info.has_audio), None)
    if audio_index is not None:
        command.extend([
            "-map", f"{audio_index}:a:0",
            "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
        ])
    else:
        command.append("-an")

    command.extend([
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-shortest",
        "-progress", "pipe:1", "-nostats", temp_output,
    ])
    return command


class VideoMergeWorker(QThread):
    progress_changed = pyqtSignal(int)
    status_changed = pyqtSignal(str)
    completed = pyqtSignal(str)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, input_paths: list[str], output_path: str, layout: str, order_code: str):
        super().__init__()
        self.input_paths = list(input_paths)
        self.output_path = os.path.abspath(output_path)
        self.layout = layout
        self.order_code = order_code
        output = Path(self.output_path)
        self.temp_output = str(output.with_name(f"{output.stem}.part{output.suffix}"))
        self._process: subprocess.Popen[str] | None = None
        self._cancel_requested = threading.Event()
        self._logger = self._create_logger()

    @staticmethod
    def _create_logger() -> logging.Logger:
        logger = logging.getLogger("multiplay.merge")
        if not logger.handlers:
            log_dir = Path(get_app_root()) / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(log_dir / "multiplay_merge.log", encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def run(self) -> None:
        stderr_tail: list[str] = []
        try:
            self.status_changed.emit("Đang kiểm tra video…")
            validate_merge_inputs(self.input_paths, self.output_path)
            if os.path.exists(self.temp_output):
                os.remove(self.temp_output)
            ffmpeg = find_ffmpeg()
            infos = [probe_video(path, self._logger) for path in self.input_paths]
            durations = [info.duration for info in infos if info.duration and info.duration > 0]
            duration = min(durations) if len(durations) == len(infos) else None
            if duration is None:
                self.progress_changed.emit(-1)
            self.status_changed.emit(f"Đang chuẩn hoá {len(self.input_paths)} video…")
            command = build_ffmpeg_command(
                ffmpeg, self.input_paths, self.temp_output, self.layout, infos
            )
            self._logger.info(
                "START order=%s count=%d layout=%s inputs=%s output=%s command=%s",
                self.order_code, len(self.input_paths), self.layout,
                self.input_paths, self.output_path, command,
            )
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            self._process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
            )

            def collect_stderr() -> None:
                assert self._process and self._process.stderr
                for line in self._process.stderr:
                    stderr_tail.append(line.rstrip())
                    del stderr_tail[:-30]

            stderr_thread = threading.Thread(target=collect_stderr, daemon=True)
            stderr_thread.start()
            assert self._process.stdout
            for raw_line in self._process.stdout:
                if self._cancel_requested.is_set():
                    break
                key, _, value = raw_line.strip().partition("=")
                if key in {"out_time_us", "out_time_ms"} and duration:
                    percent = min(99, max(0, int((int(value) / 1_000_000) / duration * 100)))
                    self.progress_changed.emit(percent)
                    self.status_changed.emit(f"Đang ghép: {percent}%")

            return_code = self._process.wait()
            stderr_thread.join(timeout=1)
            if self._cancel_requested.is_set():
                self._cleanup_temp()
                self._logger.info("CANCELLED order=%s", self.order_code)
                self.cancelled.emit()
                return
            if return_code != 0:
                detail = "\n".join(stderr_tail[-8:]) or f"Mã lỗi FFmpeg: {return_code}"
                raise RuntimeError(f"FFmpeg ghép video thất bại.\n{detail}")
            if not os.path.isfile(self.temp_output):
                raise RuntimeError("FFmpeg không tạo được file kết quả.")
            os.replace(self.temp_output, self.output_path)
            self.progress_changed.emit(100)
            self._logger.info("SUCCESS order=%s output=%s", self.order_code, self.output_path)
            self.completed.emit(self.output_path)
        except Exception as exc:
            self._cleanup_temp()
            self._logger.exception("FAILED order=%s error=%s", self.order_code, exc)
            self.failed.emit(str(exc))
        finally:
            self._process = None

    def cancel(self) -> None:
        self._cancel_requested.set()
        process = self._process
        if not process or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()

    def _cleanup_temp(self) -> None:
        try:
            if os.path.exists(self.temp_output):
                os.remove(self.temp_output)
        except OSError as exc:
            self._logger.warning("Không xoá được file tạm %s: %s", self.temp_output, exc)
