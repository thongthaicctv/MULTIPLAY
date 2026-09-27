# MULTIPLAY STORAGE + PLAYBACK CHECKPOINT — 2026-09-26

- Project: `ATG_DIGICAM_MULTIPLAY` (`D:\PYTHON\ATG_DIGICAM_MULTIPLAY`)
- Date: 2026-09-26
- Runtime: Python 3.10.11 (.venv), PyQt6 6.11 / Qt 6.11.2, python-vlc 3.0.21203, libVLC 3.0.23 x64 (`C:\Program Files\VideoLAN\VLC`)
- Base commit: `76161f8` (chore: clean repository and rename ATG_DIGICAM_MULTIPLAY)
- EXE: **CHƯA BUILD**. Chưa push.

## 1. Mục tiêu phase
MultiPlay đọc Database và tìm đúng video ở **LOCAL hoặc NAS**, đồng thời phát video (Local và UNC/NAS) ổn định trong VLC embedded, giữ nguyên nghiệp vụ nhiều video/grid/timeline/ghép video.

## 2. Storage resolver (Storage 1B)
Files: `core/database_reader.py`, `core/video_path_resolver.py`, `tests/test_video_path_resolver.py`.

- `DatabaseReader.load_video_index()` giữ interface cũ `{order_code: [resolved_path, ...]}` — `ui/main_window.py` không đổi.
- Query `packing_videos` đọc thêm `id, relative_path, storage_code, file_name`; nếu DB thiếu cột (MySQL 1054) tự dùng query cũ.
- **Local-first:** file Local tồn tại → dùng ngay (kiểm tra đồng bộ như trước; không bao giờ kiểm tra đường dẫn UNC trên UI thread).
- **NAS-background:** Local không còn → `RemoteVideoResolver` resolve trên worker thread nền; UI chỉ đọc cache (`lookup`) và đưa vào hàng đợi (`submit`), video NAS xuất hiện ở lần refresh kế tiếp.
- Thứ tự ứng viên: root đúng `storage_code` + `relative_path` → root khác + `relative_path` → root + đuôi `file_path` cũ (`<ngày>\<file>`, rồi 3 cấp) → root + `file_name`. Mỗi ứng viên là 1 đường dẫn cụ thể — **không scan / không os.walk**.
- Roots: bảng `storage_locations` (cache 60s) + `storage_path` config. Không hard-code NAS.
- NAS offline: probe root có timeout 2s trên thread nền, backoff 60s; not-found thử lại sau 5 phút.
- Log `[STORAGE] LOCAL HIT / LOCAL MISS / NAS HIT / NAS DEFERRED / NOT FOUND / ROOT ONLINE|OFFLINE / index: …`, giới hạn 50 dòng/loại (`ATG_STORAGE_LOG_LIMIT`), không log credential.
- Chỉ đọc DB. Không migration / ALTER / UPDATE / DELETE.

### DB đã xác nhận
- `packing_videos`: `id, order_code, storage_code, file_path, relative_path, file_name, camera_name, created_at, …`
- `storage_locations`: `id, storage_code, storage_name, storage_type, base_path, machine_name, ip_address, is_active, created_at, updated_at`
- `NAS01` → `\\192.168.23.200\cameraSihn`
- `LOCAL_BUIDUYTHONG-X04` → `D:\VIDEO_DEBUG`

## 3. VLC playback
### Root cause (isolation thực tế trên Windows, quan sát bằng mắt)
- LOCAL: `--file-caching=150` → video HEVC `.ts` đứng/kẹt hình khi embed Qt.
- NAS UNC: `--network-caching=150` → đứng/kẹt hình.
- `--quiet`, `--drop-late-frames`, `--skip-frames`: không gây lỗi.

### VLC options production cuối cùng (`ui/player_vlc_widget.py`)
```
--quiet
--drop-late-frames
--skip-frames
```
KHÔNG thêm lại `--file-caching`, `--network-caching`, `--avcodec-hw` hoặc option mới.

### Lifecycle EMBED-1B
`PlayerVLC.play(path)` lưu pending path; nếu widget chưa visible thì đợi `showEvent` → lấy HWND ổn định → `set_hwnd` → `media_new`/`set_media` → `play()`. `stop()` hủy pending playback.

## 4. Windows acceptance (người dùng xác nhận bằng mắt)
| Test | Kết quả |
|---|---|
| Local `862409027636_C2_NA_20260926_102732.ts` — chạy liên tục đến hết timeline | PASS |
| NAS-only `SPXVN069409531289_C2_NA_20260926_102201.ts` — DB → resolver NAS → phát UNC | PASS |
| Record mới | PASS |
| `test4camera` còn Local — phát nhiều camera đồng thời | PASS |
| `test4camera` sau khi chuyển NAS, Local không còn — 5 video NAS phát đồng thời, UI không treo, timeline chạy | PASS |

## 5. Regression (checkpoint 1I)
- Compile 24 file `.py`: 0 lỗi.
- `tests.test_video_path_resolver` + `tests.test_ffmpeg_locator`: 13 tests OK (môi trường audit Python 3.10.12).
- `tests.test_video_merge_worker`: cần PyQt6 — chạy trên Windows `.venv`.
- Bắt buộc chạy lại bằng `.venv\Scripts\python.exe` (3.10.11) trên Windows trước khi commit.

## 6. Files trong checkpoint
- `core/database_reader.py`
- `core/video_path_resolver.py` (mới)
- `tests/test_video_path_resolver.py` (mới)
- `ui/player_vlc_widget.py`
- `MULTIPLAY_STORAGE_PLAYBACK_CHECKPOINT_2026-09-26.md` (mới)

## 7. Files cố ý loại trừ (giữ nguyên working tree)
- `config.json` — cấu hình máy thực tế, có credential DB/RTSP.
- `core/video_merge_worker.py`, `tests/test_video_merge_worker.py`, `ui/main_window.py` — thay đổi Phase 2 ghép video có từ trước, không thuộc phase này.
- `tests/__init__.py` — có từ trước (2026-09-20), không cần cho unittest hiện tại.
- `vlc_diag_test.txt` — log diagnostic VLC (untracked), không commit.
- Script test `D:\tmp\atg_vlc_*.py` — ngoài repo.

## 8. Known limitations / deferred
- Video chỉ có trên NAS xuất hiện chậm hơn 1 nhịp refresh (~5–10s) sau khi mở app.
- Lần đầu có hàng nghìn record legacy đã chuyển NAS, worker nền cần thời gian resolve.
- DB refresh 5s vẫn chạy trên UI thread (kiểm tra file Local như trước).
- `.venv` activate scripts còn trỏ đường dẫn cũ `D:\PYTHON\MULTIPLAY` — cần xử lý trước khi build EXE.
- SECURITY-1B (config.json/license credential trong Git history) chưa xử lý.
- Chưa build EXE; chưa push.
