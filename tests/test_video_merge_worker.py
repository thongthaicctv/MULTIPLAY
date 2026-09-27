import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.video_merge_worker import (
    MAX_CANVAS_HEIGHT,
    MAX_CANVAS_WIDTH,
    VideoMergeWorker,
    build_ffmpeg_command,
    cell_size,
    ffmpeg_creationflags,
    is_unc_path,
    layout_shape,
    local_missing_paths,
    normalize_mp4_output_path,
    parse_progress_percent,
    resolve_layout,
    validate_merge_inputs,
)
from core.video_probe import VideoInfo


class VideoMergeCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def make_inputs(self, suffixes):
        result = []
        for index, suffix in enumerate(suffixes):
            path = self.root / f"video tiếng Việt {index}{suffix}"
            path.touch()
            result.append(str(path))
        return result

    def command(self, paths, layout="auto", audio_index=None, dimensions=None):
        dimensions = dimensions or [(1920, 1080)] * len(paths)
        infos = [
            VideoInfo(
                width=dimensions[i][0],
                height=dimensions[i][1],
                duration=10,
                has_audio=i == audio_index,
            )
            for i in range(len(paths))
        ]
        return build_ffmpeg_command("ffmpeg", paths, str(self.root / "out.part.mp4"), layout, infos)

    @staticmethod
    def filters(command):
        return command[command.index("-filter_complex") + 1]

    def test_two_mp4_auto_uses_vertical_stack(self):
        command = self.command(self.make_inputs([".mp4", ".mp4"]))
        filters = self.filters(command)
        self.assertIn("vstack=inputs=2", filters)
        self.assertIn("scale=1920:1080", filters)
        self.assertIn("pad=1920:1080", filters)
        self.assertNotIn("scale=640:360", filters)
        self.assertNotIn("shell=True", command)

    def test_two_full_hd_horizontal_produces_3840_by_1080_canvas(self):
        command = self.command(self.make_inputs([".mp4", ".mp4"]), "horizontal")
        filters = self.filters(command)
        self.assertIn("pad=1920:1080", filters)
        self.assertIn("hstack=inputs=2", filters)

    def test_two_mkv_are_accepted(self):
        paths = self.make_inputs([".mkv", ".mkv"])
        validate_merge_inputs(paths, str(self.root / "out.mp4"))

    def test_mixed_mkv_and_mp4_keep_argument_boundaries(self):
        paths = self.make_inputs([".mkv", ".mp4"])
        command = self.command(paths)
        self.assertIn(paths[0], command)
        self.assertIn(paths[1], command)

    def test_three_video_auto_uses_padded_grid(self):
        command = self.command(self.make_inputs([".mp4"] * 3))
        filters = self.filters(command)
        self.assertIn("xstack=inputs=3", filters)
        self.assertIn("pad=3840:2160", filters)

    def test_four_video_grid(self):
        command = self.command(self.make_inputs([".mp4"] * 4), "grid")
        filters = self.filters(command)
        self.assertIn("1920_1080", filters)
        self.assertIn("pad=3840:2160", filters)
        self.assertIn("-shortest", command)

    def test_mixed_resolution_uses_fixed_presentation_cell(self):
        command = self.command(
            self.make_inputs([".mp4", ".mp4"]),
            dimensions=[(1920, 1080), (1280, 720)],
        )
        filters = self.filters(command)
        self.assertIn("[0:v]scale=1920:1080", filters)
        self.assertIn("[1:v]scale=1920:1080", filters)
        self.assertEqual(filters.count("pad=1920:1080"), 2)
        self.assertIn("force_original_aspect_ratio=decrease", filters)

    def test_high_resolution_source_is_scaled_to_presentation_cell(self):
        command = self.command(
            self.make_inputs([".mp4", ".mp4"]),
            dimensions=[(1920, 1080), (2880, 1624)],
        )
        filters = self.filters(command)
        self.assertEqual(filters.count("scale=1920:1080"), 2)
        self.assertEqual(filters.count("pad=1920:1080"), 2)
        self.assertIn("vstack=inputs=2", filters)

    def test_missing_probe_dimensions_still_use_presentation_cell(self):
        command = self.command(
            self.make_inputs([".mp4", ".mp4"]),
            dimensions=[(0, 0), (1920, 1080)],
        )
        filters = self.filters(command)
        self.assertIn("[0:v]scale=1920:1080", filters)
        self.assertIn("pad=1920:1080", filters)

    def test_quality_flags_prefer_source_quality(self):
        command = self.command(self.make_inputs([".mp4", ".mp4"]))
        filters = self.filters(command)
        self.assertEqual(command[command.index("-c:v") + 1], "libx264")
        self.assertEqual(command[command.index("-preset") + 1], "slow")
        self.assertEqual(command[command.index("-crf") + 1], "15")
        self.assertEqual(command[command.index("-pix_fmt") + 1], "yuv420p")
        self.assertNotIn("18", command)
        self.assertNotIn("23", command)
        self.assertNotIn("fps=25", filters)
        self.assertNotIn("scale=640:360", filters)

    def test_filter_does_not_force_25_fps(self):
        command = self.command(self.make_inputs([".mp4", ".mp4"]))
        self.assertNotIn("fps=25", self.filters(command))

    def test_first_available_audio_is_mapped_only_once(self):
        command = self.command(self.make_inputs([".mp4"] * 3), audio_index=1)
        self.assertIn("1:a:0", command)
        self.assertNotIn("0:a:0", command)
        self.assertEqual(command.count("-c:a"), 1)

    def test_no_audio_outputs_without_audio(self):
        command = self.command(self.make_inputs([".mp4", ".mkv"]))
        self.assertIn("-an", command)

    def test_rejects_one_video(self):
        with self.assertRaisesRegex(ValueError, "ít nhất 2"):
            validate_merge_inputs(self.make_inputs([".mp4"]), str(self.root / "out.mp4"))

    def test_rejects_six_videos(self):
        with self.assertRaisesRegex(ValueError, "tối đa 5"):
            validate_merge_inputs(self.make_inputs([".mp4"] * 6), str(self.root / "out.mp4"))

    def test_rejects_missing_input(self):
        paths = self.make_inputs([".mp4", ".mkv"])
        os.remove(paths[1])
        with self.assertRaisesRegex(ValueError, "Không tồn tại"):
            validate_merge_inputs(paths, str(self.root / "out.mp4"))

    def test_rejects_output_equal_to_input(self):
        paths = self.make_inputs([".mp4", ".mkv"])
        with self.assertRaisesRegex(ValueError, "không được trùng"):
            validate_merge_inputs(paths, paths[0])

    def test_explicit_vertical_layout(self):
        command = self.command(self.make_inputs([".mp4", ".mkv"]), "vertical")
        filters = self.filters(command)
        self.assertIn("vstack=inputs=2", filters)

    def test_existing_output_is_validated_by_ui_policy(self):
        paths = self.make_inputs([".mp4", ".mkv"])
        output = self.root / "existing.mp4"
        output.touch()
        validate_merge_inputs(paths, str(output))

    def test_auto_layout_rules(self):
        self.assertEqual(resolve_layout("auto", 2), "vertical")
        self.assertEqual(resolve_layout("auto", 3), "grid")
        self.assertEqual(resolve_layout("auto", 4), "grid")


class VideoMergeHotfixTests(unittest.TestCase):
    def test_progress_na_is_ignored(self):
        self.assertIsNone(parse_progress_percent("N/A", 10.0))

    def test_malformed_progress_is_ignored(self):
        self.assertIsNone(parse_progress_percent("", 10.0))
        self.assertIsNone(parse_progress_percent(None, 10.0))

    def test_numeric_and_negative_progress(self):
        self.assertEqual(parse_progress_percent("5000000", 10.0), 50)
        self.assertEqual(parse_progress_percent("-1000", 10.0), 0)

    def test_output_suffix_is_replaced_with_mp4(self):
        self.assertEqual(
            normalize_mp4_output_path(r"D:\VIDEO_DEBUG\merged.mkv"),
            r"D:\VIDEO_DEBUG\merged.mp4",
        )
        self.assertEqual(
            normalize_mp4_output_path(r"D:\VIDEO_DEBUG\merged"),
            r"D:\VIDEO_DEBUG\merged.mp4",
        )

    def test_worker_final_and_temp_outputs_are_mp4(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(
            VideoMergeWorker, "_create_logger"
        ):
            worker = VideoMergeWorker(
                ["camera1.ts", "camera2.ts"],
                str(Path(folder) / "merged.ts"),
                "vertical",
                "ORDER",
            )
            self.assertTrue(worker.output_path.endswith("merged.mp4"))
            self.assertTrue(worker.temp_output.endswith("merged.part.mp4"))

    def test_stop_process_reaps_before_temp_cleanup(self):
        events = []

        class FakeProcess:
            def poll(self):
                events.append("poll")
                return None

            def terminate(self):
                events.append("terminate")

            def wait(self, timeout=None):
                events.append(f"wait:{timeout}")
                return 0

            def kill(self):
                events.append("kill")

        with tempfile.TemporaryDirectory() as folder, patch.object(
            VideoMergeWorker, "_create_logger"
        ):
            worker = VideoMergeWorker(
                ["camera1.ts", "camera2.ts"],
                str(Path(folder) / "merged.mp4"),
                "vertical",
                "ORDER",
            )
            Path(worker.temp_output).touch()
            worker._process = FakeProcess()
            worker._stop_process()
            events.append("cleanup")
            worker._cleanup_temp()

        self.assertEqual(events, ["poll", "terminate", "wait:2", "cleanup"])

    def test_stop_process_kills_and_reaps_after_timeout(self):
        events = []

        class SlowProcess:
            wait_count = 0

            def poll(self):
                return None

            def terminate(self):
                events.append("terminate")

            def wait(self, timeout=None):
                self.wait_count += 1
                events.append(f"wait:{timeout}")
                if self.wait_count == 1:
                    raise __import__("subprocess").TimeoutExpired("ffmpeg", timeout)
                return 0

            def kill(self):
                events.append("kill")

        with tempfile.TemporaryDirectory() as folder, patch.object(
            VideoMergeWorker, "_create_logger"
        ):
            worker = VideoMergeWorker(
                ["camera1.ts", "camera2.ts"],
                str(Path(folder) / "merged.mp4"),
                "vertical",
                "ORDER",
            )
            worker._process = SlowProcess()
            worker._stop_process()

        self.assertEqual(events, ["terminate", "wait:2", "kill", "wait:2"])


if __name__ == "__main__":
    unittest.main()


# ===================== MULTIPLAY-VIDEO-MERGE-HARDENING-2B =====================
import ast
import re
import subprocess
import threading

UNC_ROOT = r"\\nas-test\share\2026-09-26"


def _infos(count, audio_index=None, size=(1920, 1080)):
    return [
        VideoInfo(width=size[0], height=size[1], duration=10, has_audio=i == audio_index)
        for i in range(count)
    ]


def _filters(command):
    return command[command.index("-filter_complex") + 1]


def _canvas(command, count, layout):
    """Kich thuoc canvas cuoi (tinh tu cell + so cot/hang trong filter)."""
    filters = _filters(command)
    cell_w, cell_h = map(int, re.search(r"pad=(\d+):(\d+):\(ow-iw\)", filters).groups())
    grid_pad = re.search(r"\[vgrid\]pad=(\d+):(\d+)", filters)
    if grid_pad:
        return int(grid_pad.group(1)), int(grid_pad.group(2))
    if "hstack" in filters:
        return cell_w * count, cell_h
    return cell_w, cell_h * count


def _cmd(paths, layout="auto", audio_index=None, size=(1920, 1080)):
    return build_ffmpeg_command(
        "ffmpeg", paths, r"D:\\out\\merged.part.mp4", layout, _infos(len(paths), audio_index, size)
    )


class MergeLayoutHardeningTests(unittest.TestCase):
    PATHS = [rf"D:\\VIDEO_DEBUG\\2026-09-26\\cam {i}.ts" for i in range(5)]

    def test_auto_2_is_vertical_1920x2160(self):
        command = _cmd(self.PATHS[:2])
        self.assertIn("vstack=inputs=2", _filters(command))
        self.assertEqual(_canvas(command, 2, "auto"), (1920, 2160))

    def test_auto_3_is_2x2_with_empty_cell(self):
        command = _cmd(self.PATHS[:3])
        f = _filters(command)
        self.assertIn("xstack=inputs=3:layout=0_0|1920_0|0_1080", f)
        self.assertEqual(_canvas(command, 3, "auto"), (3840, 2160))

    def test_auto_4_is_2x2(self):
        command = _cmd(self.PATHS[:4])
        self.assertIn("layout=0_0|1920_0|0_1080|1920_1080", _filters(command))
        self.assertEqual(_canvas(command, 4, "auto"), (3840, 2160))

    def test_auto_5_is_3x2_with_empty_cell(self):
        self.assertEqual(resolve_layout("auto", 5), "grid")
        self.assertEqual(layout_shape("grid", 5), (3, 2))
        command = _cmd(self.PATHS[:5])
        f = _filters(command)
        self.assertIn("xstack=inputs=5:layout=0_0|1280_0|2560_0|0_1080|1280_1080", f)
        self.assertEqual(f.count("pad=1280:1080:(ow-iw)/2:(oh-ih)/2"), 5)
        self.assertEqual(_canvas(command, 5, "auto"), (3840, 2160))

    def test_all_layouts_never_exceed_3840x2160(self):
        for count in range(2, 6):
            for layout in ("auto", "horizontal", "vertical", "grid"):
                with self.subTest(count=count, layout=layout):
                    w, h = _canvas(_cmd(self.PATHS[:count], layout), count, layout)
                    self.assertLessEqual(w, MAX_CANVAS_WIDTH)
                    self.assertLessEqual(h, MAX_CANVAS_HEIGHT)
                    self.assertEqual((w % 2, h % 2), (0, 0))

    def test_horizontal_4_is_not_7680(self):
        command = _cmd(self.PATHS[:4], "horizontal")
        self.assertEqual(_canvas(command, 4, "horizontal"), (3840, 1080))
        self.assertNotIn("7680", " ".join(command))

    def test_horizontal_5_and_vertical_5_fit(self):
        self.assertEqual(_canvas(_cmd(self.PATHS, "horizontal"), 5, "horizontal"), (3840, 1080))
        self.assertEqual(_canvas(_cmd(self.PATHS, "vertical"), 5, "vertical"), (1920, 2160))

    def test_grid_5_is_not_5760(self):
        command = _cmd(self.PATHS, "grid")
        self.assertNotIn("5760", " ".join(command))

    def test_cell_size_is_even_and_capped(self):
        for cols in range(1, 6):
            for rows in range(1, 6):
                w, h = cell_size(cols, rows)
                self.assertLessEqual(w * cols, MAX_CANVAS_WIDTH)
                self.assertLessEqual(h * rows, MAX_CANVAS_HEIGHT)
                self.assertLessEqual(w, 1920)
                self.assertLessEqual(h, 1080)
                self.assertEqual((w % 2, h % 2), (0, 0))

    def test_no_crop_no_stretch_keep_aspect_and_pad(self):
        for count in range(2, 6):
            f = _filters(_cmd(self.PATHS[:count], size=(2560, 1440)))
            self.assertNotIn("crop", f)
            self.assertEqual(f.count("force_original_aspect_ratio=decrease"), count)
            self.assertEqual(f.count("(ow-iw)/2:(oh-ih)/2:black,setsar=1"), count)

    def test_quality_settings_unchanged(self):
        command = _cmd(self.PATHS)
        self.assertEqual(command[command.index("-crf") + 1], "15")
        self.assertEqual(command[command.index("-preset") + 1], "slow")
        self.assertEqual(command[command.index("-c:v") + 1], "libx264")
        self.assertEqual(command[command.index("-pix_fmt") + 1], "yuv420p")
        self.assertIn("+faststart", command)
        self.assertIn("flags=lanczos", _filters(command))
        self.assertNotIn("fps=25", _filters(command))
        self.assertNotIn("h264_nvenc", command)
        self.assertEqual(command[command.index("-f") + 1], "mp4")
        self.assertTrue(command[-1].endswith(".mp4"))
        self.assertIn("-shortest", command)


class MergePathTests(unittest.TestCase):
    def test_unc_detection(self):
        self.assertTrue(is_unc_path(r"\\192.168.23.200\cameraSihn\a.ts"))
        self.assertTrue(is_unc_path("//nas/share/a.ts"))
        self.assertFalse(is_unc_path(r"D:\VIDEO_DEBUG\a.ts"))
        self.assertFalse(is_unc_path(""))

    def test_local_unc_space_and_mixed_paths_are_single_arguments(self):
        paths = [
            r"D:\VIDEO_DEBUG\2026-09-26\ORDER_C1.ts",
            UNC_ROOT + r"\ORDER_C2.ts",
            r"D:\VIDEO DEBUG\thư mục có space\ORDER C3.ts",
            UNC_ROOT + r"\folder with space\ORDER_C4.ts",
        ]
        command = _cmd(paths)
        for path in paths:
            self.assertIn(path, command)
            self.assertEqual(command[command.index(path) - 1], "-i")
        self.assertEqual(command.count("-i"), 4)

    def test_validate_accepts_unc_inputs_in_worker(self):
        paths = [UNC_ROOT + r"\A.ts", r"D:\VIDEO_DEBUG\B.ts"]
        with tempfile.TemporaryDirectory() as folder, \
                patch("os.path.isfile", return_value=True) as isfile, \
                patch("os.access", return_value=True):
            validate_merge_inputs(paths, str(Path(folder) / "out.mp4"))
        checked = [c.args[0] for c in isfile.call_args_list]
        self.assertIn(paths[0], checked)  # UNC duoc kiem tra trong worker (ngoai UI thread)

    def test_local_missing_paths_never_probes_unc(self):
        paths = [UNC_ROOT + r"\A.ts", r"D:\missing\B.ts", "//nas/share/C.ts"]
        with patch("os.path.isfile", return_value=False) as isfile:
            missing = local_missing_paths(paths)
        self.assertEqual(missing, [r"D:\missing\B.ts"])
        self.assertEqual([c.args[0] for c in isfile.call_args_list], [r"D:\missing\B.ts"])

    def test_main_window_merge_checked_does_not_probe_unc_on_ui_thread(self):
        source = Path(__file__).resolve().parents[1].joinpath("ui", "main_window.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        method = next(
            n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "merge_checked"
        )
        calls = [ast.unparse(n.func) for n in ast.walk(method) if isinstance(n, ast.Call)]
        self.assertIn("local_missing_paths", calls)
        self.assertNotIn("os.path.isfile", calls)
        self.assertNotIn("os.stat", calls)
        # os.path.exists chi duoc goi sau khi da loai tru output UNC
        body = ast.unparse(method)
        self.assertIn("not is_unc_path(output_path) and os.path.exists(output_path)", body)
        self.assertEqual(body.count("os.path.exists("), 1)


class MergePriorityTests(unittest.TestCase):
    def test_windows_flags_below_normal_and_no_window(self):
        flags = ffmpeg_creationflags("nt")
        self.assertTrue(flags & 0x00004000)  # BELOW_NORMAL_PRIORITY_CLASS
        self.assertTrue(flags & 0x08000000)  # CREATE_NO_WINDOW
        self.assertFalse(flags & 0x00000080)  # khong HIGH_PRIORITY_CLASS

    def test_non_windows_flags_zero(self):
        self.assertEqual(ffmpeg_creationflags("posix"), 0)


class _FakeProcess:
    def __init__(self, stdout_lines, return_code=0, on_line=None, create=None):
        self._lines = list(stdout_lines)
        self._on_line = on_line
        self.return_code = return_code
        self.stderr = iter(["frame=1", "Error while decoding stream"] if return_code else [])
        self.terminated = False
        self.killed = False
        self._create = create
        self.stdout = self._stdout()

    def _stdout(self):
        for line in self._lines:
            if self._on_line:
                self._on_line(line)
            yield line

    def poll(self):
        return None if not (self.terminated or self.killed) else self.return_code

    def wait(self, timeout=None):
        if self._create:
            Path(self._create).write_bytes(b"mp4")
        return -15 if self.terminated else self.return_code

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


class MergeWorkerRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.inputs = []
        for i in range(2):
            path = self.root / f"cam {i}.ts"
            path.write_bytes(b"ts")
            self.inputs.append(str(path))
        self.output = str(self.root / "merged.mp4")
        patcher = patch.object(VideoMergeWorker, "_create_logger", return_value=unittest.mock.MagicMock())
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.temp.cleanup)

    def _worker(self):
        worker = VideoMergeWorker(self.inputs, self.output, "auto", "ORDER")
        events = {"failed": [], "completed": [], "cancelled": []}
        worker.failed.connect(lambda m: events["failed"].append(m))
        worker.completed.connect(lambda p: events["completed"].append(p))
        worker.cancelled.connect(lambda: events["cancelled"].append(True))
        return worker, events

    def _run(self, worker, process):
        popen_kwargs = {}

        def fake_popen(command, **kwargs):
            popen_kwargs.update(kwargs, command=command)
            return process

        with patch("core.video_merge_worker.find_ffmpeg", return_value="ffmpeg"), \
                patch("core.video_merge_worker.probe_video", return_value=VideoInfo(1920, 1080, 10.0)), \
                patch("core.video_merge_worker.subprocess.Popen", side_effect=fake_popen):
            worker.run()
        return popen_kwargs

    def test_success_writes_mp4_and_passes_priority_flags(self):
        worker, events = self._worker()
        process = _FakeProcess(["out_time_us=5000000", "progress=end"], create=worker.temp_output)
        kwargs = self._run(worker, process)
        self.assertEqual(events["completed"], [worker.output_path])
        self.assertTrue(os.path.isfile(self.output))
        self.assertFalse(os.path.exists(worker.temp_output))
        self.assertEqual(kwargs["creationflags"], ffmpeg_creationflags())
        self.assertNotIn("shell", kwargs)

    def test_ffmpeg_error_reports_failure_and_cleans_part(self):
        worker, events = self._worker()
        Path(worker.temp_output).write_bytes(b"partial")
        process = _FakeProcess(["out_time_us=1000000"], return_code=1)
        self._run(worker, process)
        self.assertEqual(len(events["failed"]), 1)
        self.assertIn("FFmpeg ghép video thất bại", events["failed"][0])
        self.assertFalse(os.path.exists(worker.temp_output))
        self.assertFalse(os.path.exists(self.output))

    def test_cancel_stops_process_and_cleans_part(self):
        worker, events = self._worker()

        def on_line(line):
            Path(worker.temp_output).write_bytes(b"partial")
            worker.cancel()

        process = _FakeProcess(["out_time_us=1000000", "out_time_us=2000000"], on_line=on_line)
        self._run(worker, process)
        self.assertTrue(process.terminated)
        self.assertEqual(events["cancelled"], [True])
        self.assertEqual(events["completed"], [])
        self.assertFalse(os.path.exists(worker.temp_output))
        self.assertFalse(os.path.exists(self.output))
