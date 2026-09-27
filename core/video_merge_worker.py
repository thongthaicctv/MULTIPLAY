"""Worker ghép đồng thời 2-5 video bằng FFmpeg."""

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
PRESENTATION_WIDTH = 1920
PRESENTATION_HEIGHT = 1080
# MULTIPLAY-VIDEO-MERGE-HARDENING-2B: gioi han video dau vao va kich thuoc canvas
MIN_INPUTS = 2
MAX_INPUTS = 5
MAX_CANVAS_WIDTH = 3840
MAX_CANVAS_HEIGHT = 2160

# Windows process creation flags (dinh nghia lai de dung duoc tren moi OS)
_CREATE_NO_WINDOW = 0x08000000
_BELOW_NORMAL_PRIORITY_CLASS = 0x00004000


def is_unc_path(path: str) -> bool:
    """Duong dan mang UNC (dang //server/share hoac 2 dau backslash) - KHONG probe tren UI thread."""
    value = str(path or "")
    return value.startswith("\\\\") or value.startswith("//")


def local_missing_paths(input_paths: list[str]) -> list[str]:
    """Kiem tra nhanh file LOCAL cho UI; bo qua UNC (worker se validate ngoai UI thread)."""
    return [path for path in input_paths if not is_unc_path(path) and not os.path.isfile(path)]


def ffmpeg_creationflags(os_name: str | None = None) -> int:
    """Windows: an cua so console + uu tien BELOW_NORMAL de khong tranh CPU voi playback/UI."""
    if (os_name or os.name) != "nt":
        return 0
    return (
        getattr(subprocess, "CREATE_NO_WINDOW", _CREATE_NO_WINDOW)
        | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", _BELOW_NORMAL_PRIORITY_CLASS)
    )


def layout_shape(resolved_layout: str, count: int) -> tuple[int, int]:
    """(so cot, so hang) cua bo cuc."""
    if resolved_layout == "horizontal":
        return count, 1
    if resolved_layout == "vertical":
        return 1, count
    return (3, 2) if count == 5 else (2, 2)


def cell_size(cols: int, rows: int) -> tuple[int, int]:
    """O cho moi camera: toi da 1920x1080, canvas toi da 3840x2160, kich thuoc chan."""
    cell_w = min(PRESENTATION_WIDTH, MAX_CANVAS_WIDTH // cols)
    cell_h = min(PRESENTATION_HEIGHT, MAX_CANVAS_HEIGHT // rows)
    return cell_w - cell_w % 2, cell_h - cell_h % 2


def normalize_mp4_output_path(output_path: str) -> str:
    path = Path(output_path)
    if path.suffix.lower() == ".mp4":
        return str(path)
    return str(path.with_suffix(".mp4"))


def parse_progress_percent(value: str | None, duration: float | None) -> int | None:
    if not duration or duration <= 0:
        return None
    try:
        progress_us = int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
    if progress_us is None:
        return None
    return min(99, max(0, int((progress_us / 1_000_000) / duration * 100)))


def validate_merge_inputs(input_paths: list[str], output_path: str) -> None:
    if len(input_paths) < MIN_INPUTS:
        raise ValueError("Vui lòng chọn ít nhất 2 video để ghép.")
    if len(input_paths) > MAX_INPUTS:
        raise ValueError("Chỉ hỗ trợ ghép tối đa 5 video.")
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
        # Ưu tiên bố cục dọc cho 2 video: video 1 trên, video 2 dưới.
        # 3-4 video: lưới 2x2; 5 video: lưới 3 cột x 2 hàng (xem layout_shape).
        return "vertical" if count == 2 else "grid"
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

    cols, rows = layout_shape(resolved, count)
    cell_w, cell_h = cell_size(cols, rows)

    filters = []
    for index in range(count):
        filters.append(
            f"[{index}:v]scale={cell_w}:{cell_h}:force_original_aspect_ratio=decrease:"
            "force_divisible_by=2:flags=lanczos,"
            f"pad={cell_w}:{cell_h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1[v{index}]"
        )

    labels = "".join(f"[v{i}]" for i in range(count))
    if resolved == "horizontal":
        filters.append(f"{labels}hstack=inputs={count}[vout]")
    elif resolved == "vertical":
        filters.append(f"{labels}vstack=inputs={count}[vout]")
    else:
        positions = [f"{(i % cols) * cell_w}_{(i // cols) * cell_h}" for i in range(count)]
        filters.append(
            f"{labels}xstack=inputs={count}:layout={'|'.join(positions)}:"
            "fill=black[vgrid]"
        )
        filters.append(
            f"[vgrid]pad={cell_w * cols}:{cell_h * rows}:0:0:black[vout]"
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
        "-c:v", "libx264", "-preset", "slow", "-crf", "15",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-shortest",
        "-progress", "pipe:1", "-nostats", "-f", "mp4", temp_output,
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
        self.output_path = os.path.abspath(normalize_mp4_output_path(output_path))
        self.layout = layout
        self.order_code = order_code
        output = Path(self.output_path)
        self.temp_output = str(output.with_name(f"{output.stem}.part.mp4"))
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
            creationflags = ffmpeg_creationflags()
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
                    percent = parse_progress_percent(value, duration)
                    if percent is None:
                        continue
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
            self._stop_process()
            self._cleanup_temp()
            self._logger.exception("FAILED order=%s error=%s", self.order_code, exc)
            self.failed.emit(str(exc))
        finally:
            self._process = None

    def cancel(self) -> None:
        self._cancel_requested.set()
        self._stop_process()

    def _stop_process(self) -> None:
        process = self._process
        if not process or process.poll() is not None:
            return
        try:
            process.terminate()
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
                process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired) as exc:
                self._logger.warning("Không thể reap FFmpeg sau khi kill: %s", exc)
        except OSError as exc:
            self._logger.warning("Không thể dừng FFmpeg: %s", exc)

    def _cleanup_temp(self) -> None:
        try:
            if os.path.exists(self.temp_output):
                os.remove(self.temp_output)
        except OSError as exc:
            self._logger.warning("Không xoá được file tạm %s: %s", self.temp_output, exc)
