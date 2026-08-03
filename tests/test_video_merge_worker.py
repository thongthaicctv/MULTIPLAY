import os
import tempfile
import unittest
from pathlib import Path

from core.video_merge_worker import (
    build_ffmpeg_command,
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

    def command(self, paths, layout="auto", audio_index=None):
        infos = [VideoInfo(duration=10, has_audio=i == audio_index) for i in range(len(paths))]
        return build_ffmpeg_command("ffmpeg", paths, str(self.root / "out.part.mp4"), layout, infos)

    def test_two_mp4_auto_uses_horizontal_stack(self):
        command = self.command(self.make_inputs([".mp4", ".mp4"]))
        filters = command[command.index("-filter_complex") + 1]
        self.assertIn("hstack=inputs=2", filters)
        self.assertNotIn("shell=True", command)

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
        filters = command[command.index("-filter_complex") + 1]
        self.assertIn("xstack=inputs=3", filters)
        self.assertIn("pad=1280:720", filters)

    def test_four_video_grid(self):
        command = self.command(self.make_inputs([".mp4"] * 4), "grid")
        filters = command[command.index("-filter_complex") + 1]
        self.assertIn("640_360", filters)
        self.assertIn("-shortest", command)

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

    def test_rejects_five_videos(self):
        with self.assertRaisesRegex(ValueError, "tối đa 4"):
            validate_merge_inputs(self.make_inputs([".mp4"] * 5), str(self.root / "out.mp4"))

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
        filters = command[command.index("-filter_complex") + 1]
        self.assertIn("vstack=inputs=2", filters)

    def test_existing_output_is_validated_by_ui_policy(self):
        paths = self.make_inputs([".mp4", ".mkv"])
        output = self.root / "existing.mp4"
        output.touch()
        validate_merge_inputs(paths, str(output))

    def test_auto_layout_rules(self):
        self.assertEqual(resolve_layout("auto", 2), "horizontal")
        self.assertEqual(resolve_layout("auto", 3), "grid")
        self.assertEqual(resolve_layout("auto", 4), "grid")


if __name__ == "__main__":
    unittest.main()
