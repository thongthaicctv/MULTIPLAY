# ATG_DIGICAM_MULTIPLAY Official Release

Date: 2026-09-27

Source checkpoint:
20c76011ec62368081f18ad1eb4429cd432a67b9 (checkpoint: harden MultiPlay video merge local and NAS)

Windows runtime:
Python 3.10.11 (x64, project .venv)

Regression:
61/61 PASS (tests.test_video_merge_worker, tests.test_video_path_resolver, tests.test_ffmpeg_locator)

Acceptance (Windows, người dùng xác nhận):
- EXE startup PASS
- Local playback PASS
- NAS playback PASS
- Local merge PASS
- NAS merge PASS

Release EXE:
ATG_DIGICAM_MULTIPLAY.exe (PyInstaller onefile, build từ ATG-MultiPlay.spec, 218,823,068 bytes)

SHA256:
CBA4E1A8487C9E18E4F978519FC081F94982483356EF1B94DB71E6851D3CDC62

Deployment requirement:
- config.json đặt cạnh EXE (EXE không chứa config/credential)
- VLC 64-bit phải được cài trên máy chạy (C:\Program Files\VideoLAN\VLC)
- FFmpeg/ffprobe đã được đóng kèm theo cơ chế packaging hiện tại (bin\ trong EXE)

Known deferred items:
- camera start-time synchronization: deferred
- mixed Local+NAS merge acceptance: not required for this release
