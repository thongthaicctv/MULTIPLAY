# MULTIPLAY VIDEO MERGE CHECKPOINT — 2026-09-27

- Project: `ATG_DIGICAM_MULTIPLAY` (`D:\PYTHON\ATG_DIGICAM_MULTIPLAY`)
- Phase: MULTIPLAY-VIDEO-MERGE-HARDENING-2B → checkpoint 2C
- Base commit: `141e688` (checkpoint: MultiPlay local/NAS storage playback acceptance)
- EXE: **CHƯA BUILD**. Chưa push.

## Windows acceptance (người dùng xác nhận)
| Hạng mục | Kết quả |
|---|---|
| Môi trường | project `.venv`, Python 3.10.11 |
| Regression | 61/61 PASS |
| Local merge | PASS |
| NAS merge | PASS |
| Playback Local/NAS | PASS (checkpoint `141e688`, không thay đổi) |

## Phase 2B behavior
- Hỗ trợ 2–5 video trong code; production thường dùng tối đa 4 camera.
- AUTO 2 video = dọc 1 cột x 2 hàng (1920x2160).
- AUTO 3–4 video = lưới 2x2 (3840x2160, 3 video có 1 ô trống).
- AUTO 5 video = lưới 3 cột x 2 hàng (ô 1280x1080, canvas 3840x2160).
- Canvas output luôn <= 3840x2160 cho mọi layout (auto / horizontal / vertical / grid); ô chẵn.
- Không kiểm tra filesystem UNC/NAS trên UI thread (`local_missing_paths` bỏ qua UNC; worker validate ngoài UI thread; output UNC không probe trên UI).
- FFmpeg chạy `BELOW_NORMAL_PRIORITY_CLASS` + `CREATE_NO_WINDOW` trên Windows.
- Chất lượng giữ nguyên: libx264 / preset slow / CRF 15 / yuv420p / +faststart / scale lanczos.
- Không ép `fps=25`.
- Không crop / không stretch: `force_original_aspect_ratio=decrease` + `pad` + `setsar=1`.
- Output MP4 (`.part.mp4` → `os.replace`), cleanup khi lỗi / hủy.
- Nhận trực tiếp đường dẫn đã resolve: Local, UNC/NAS, hoặc trộn; không copy NAS về local; không hard-code NAS.
- Audio: lấy từ video đầu tiên có audio (AAC 128k / 48 kHz / stereo), không có thì `-an`.

## Files trong checkpoint
- `core/video_merge_worker.py`
- `ui/main_window.py` (chỉ import + `merge_checked`)
- `tests/test_video_merge_worker.py`
- `MULTIPLAY_VIDEO_MERGE_CHECKPOINT_2026-09-27.md`

## Files cố ý loại trừ
- `config.json` (cấu hình máy thực tế, có credential)
- `tests/__init__.py` (có từ trước, không cần)
- `vlc_diag_test.txt` (log diagnostic)

## Known limitations (giữ cho phase sau — KHÔNG sửa trong checkpoint này)
- Camera start-time synchronization chưa triển khai (mỗi video ghép từ đầu file).
- `-shortest` giữ nguyên (output dừng theo video ngắn nhất).
- CRF 15 + preset slow có thể tốn nhiều CPU / thời gian, file lớn.
- Hỗ trợ 5 camera có trong code nhưng không phải yêu cầu production thường xuyên.
- `ffprobe` chạy độ ưu tiên thường (ngắn).
