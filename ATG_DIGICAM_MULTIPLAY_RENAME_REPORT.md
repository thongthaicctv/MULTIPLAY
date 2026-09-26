# ATG_DIGICAM_MULTIPLAY – RENAME REPORT

Ngày: 2026-09-26

## OLD PATH
`D:\PYTHON\MULTIPLAY`
(xác định qua `.venv\Scripts\activate.bat`, launcher `.venv\Scripts\*.exe` và traceback trong `logs\multiplay_merge.log`)

## NEW PATH
`D:\PYTHON\ATG_DIGICAM_MULTIPLAY`

Trạng thái move: thư mục **đã ở đường dẫn mới trước khi phiên này bắt đầu**; `D:\PYTHON\MULTIPLAY` không còn tồn tại.
Không clone lại, không move thêm. `.git`, source, config, bin (ffmpeg/ffprobe), resource, tests, tài liệu đều còn đủ.

## GIT
- branch: `main` (up to date with `origin/main`)
- remote: `origin https://github.com/thongthaicctv/ATG_DIGICAM_MULTIPLAY.git` (fetch/push)
- HEAD: `0c731d5 Update MultiPlay Phase 2` – 7 commit, lịch sử nguyên vẹn, `git fsck --connectivity-only` OK
- status: có thay đổi chưa commit **có sẵn từ trước** (không do bước rename):
  - Nội dung thật: `config.json`, `core/video_merge_worker.py`, `ui/main_window.py`, `tests/test_video_merge_worker.py`, `logs/multiplay_merge.log`, các `__pycache__/*.pyc`
  - Untracked: `__pycache__/`, `bin/`, `build/`, `dist/`, `tests/__init__.py`
  - Nhiều file khác (kể cả trong `.venv/`, vốn đang được track trong Git) chỉ khác CRLF/whitespace
- Không commit, không push.

## FILES MODIFIED
NONE (không sửa code, config, DB hay build script).

Ghi chú: một lần `git status` trong lúc audit để lại file khóa tạm `.git/index.lock` (0 byte, do chính bước audit tạo ra). File này đã được xóa để Git không bị chặn. Không xóa file nào khác.

## HARD-CODED PATH FOUND
| Vị trí | Trỏ tới | Ảnh hưởng | Xử lý |
|---|---|---|---|
| `.venv\Scripts\activate`, `activate.bat` | `D:\PYTHON\MULTIPLAY\.venv` | Sau khi activate, PATH trỏ sai → `python` rơi về `C:\Python310` (không có PyQt6…) | Chưa sửa – xem khuyến nghị |
| `.venv\Scripts\pip.exe, pip3*.exe, pyinstaller.exe, pyi-*.exe, pyav.exe, f2py.exe, idna.exe, normalizer.exe, numpy-config.exe, pylupdate6.exe, pyuic6.exe` | `#!D:\PYTHON\MULTIPLAY\.venv\Scripts\python.exe` | Gọi trực tiếp sẽ lỗi "Fatal error in launcher" | Chưa sửa |
| `__pycache__/*.pyc`, `core/__pycache__`, … | đường dẫn cũ (co_filename) | Chỉ ảnh hưởng traceback, Python tự biên dịch lại | Không cần sửa |
| `build/ATG-MultiPlay/*` | đường dẫn cũ | Artifact PyInstaller, tạo lại khi build | Không cần sửa |
| `logs/multiplay_merge.log` | traceback cũ | Log lịch sử | Không cần sửa |
| `core/license_manager.py` | `C:\ProgramData\ATGMultiPlay` | Không phụ thuộc thư mục project | Không cần sửa |
| `config.json` `storage_path` | `D:/VIDEO_DEBUG` | Không phụ thuộc thư mục project | Không cần sửa |

Source code **không** có đường dẫn tuyệt đối tới thư mục project:
- `ConfigManager` đọc `config.json` cạnh `sys.argv[0]` / EXE
- `ffmpeg_locator` tìm `bin\ffmpeg.exe` theo thư mục app (tương đối `__file__`) → `_MEIPASS` → PATH
- `player_vlc_widget` tìm VLC tương đối `sys.argv[0]`
- `utils.resource_path` dùng `_MEIPASS` hoặc CWD
- `ATG-MultiPlay.spec` dùng `SPECPATH`; `build_onefile.ps1` dùng `$MyInvocation` → đều tương đối
- Không có code tham chiếu shortcut/autostart/registry.
- Không có `StorageResolver` trong project này; tìm video = `DatabaseReader` (MySQL `packing_videos.file_path`) + `storage_path` trong config + `video_index.json`.

## SMOKE TEST
Kiểm tra được từ môi trường audit (Linux, dùng đúng code của project tại đường dẫn mới):
- Biên dịch 22 file `.py`: 0 lỗi
- `ConfigManager` tìm & đọc `config.json` tại thư mục mới: OK (24 key, `storage_path = D:/VIDEO_DEBUG`, DB `127.0.0.1:3306/atg_order_system`)
- `ffmpeg_locator.get_app_root()` = thư mục mới; `bin\ffmpeg.exe`, `bin\ffprobe.exe` có mặt
- `icon.ico`, `antn.png` tìm được qua `resource_path`
- `tests.test_ffmpeg_locator`: 4/4 OK

Smoke test runtime trên Windows (kết quả thực tế đã được xác nhận):

- Python 3.10.11: PASS
- App startup: PASS
- Config load: PASS
- MySQL connection: PASS
- Order lookup: PASS
- Video lookup: PASS
- Video playback: PASS
- FFmpeg / FFprobe: PASS
- StorageResolver: N/A (không có trong MultiPlay; cơ chế tìm video không bị sửa)

Lệnh chạy smoke test trên Windows (KHÔNG dùng `activate` vì activate còn trỏ đường dẫn cũ):
```
cd /d D:\PYTHON\ATG_DIGICAM_MULTIPLAY
.venv\Scripts\python.exe main.py
```
(`.venv\Scripts\python.exe` dùng `pyvenv.cfg` → `C:\Python310`, không phụ thuộc đường dẫn cũ.)

## KHUYẾN NGHỊ
1. Sửa `.venv` cho đường dẫn mới: tạo lại venv (`python -m venv .venv` + `pip install -r requirements.txt`) **hoặc** sửa `VIRTUAL_ENV` trong 3 file activate. Bắt buộc trước khi chạy `build_onefile.ps1` (script dùng `python` từ PATH).
2. ĐÃ XỬ LÝ (Checkpoint A): bỏ `.venv/`, `*.pyc`, `logs/multiplay_merge.log` khỏi Git index (file local giữ nguyên) và thêm `.gitignore`.
3. ĐÃ XỬ LÝ: remote đã đổi sang `https://github.com/thongthaicctv/ATG_DIGICAM_MULTIPLAY.git`.

## KẾT LUẬN
RENAME SMOKE TEST: **PASS** (Windows runtime – các hạng mục đã xác nhận ở mục SMOKE TEST)

ATG_DIGICAM_MULTIPLAY RENAME: **PASS**

KHÔNG push, KHÔNG build EXE ở bước này.
