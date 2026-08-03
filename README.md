# ATG MultiPlay

Ứng dụng Windows dùng để tìm kiếm mã đơn hàng và phát đồng thời nhiều video được tạo bởi ATG Recorder. Dữ liệu video được đọc từ MySQL, sau đó hiển thị bằng giao diện PyQt6 và phát qua VLC.

## Yêu cầu hệ thống

- Windows 10/11 64-bit
- Python 3.10 trở lên (khuyến nghị Python 3.10 hoặc 3.11, 64-bit)
- VLC Media Player 64-bit
- FFmpeg (nên kèm cả `ffmpeg.exe` và `ffprobe.exe`)
- MySQL và thư mục video của ATG Recorder có thể truy cập từ máy đang chạy

> Python và VLC phải cùng kiến trúc, ví dụ đều là 64-bit. Ứng dụng tìm VLC tại `bin/vlc`, `vlc`, `C:\Program Files\VideoLAN\VLC` hoặc `C:\Program Files (x86)\VideoLAN\VLC`.

## Cài đặt trên máy mới

Mở PowerShell tại thư mục dự án và chạy:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Nếu PowerShell chặn script kích hoạt môi trường ảo, chạy lệnh sau trong cửa sổ hiện tại rồi kích hoạt lại:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Cài [VLC Media Player](https://www.videolan.org/vlc/) 64-bit nếu máy chưa có. Có thể kiểm tra nhanh:

```powershell
Test-Path "C:\Program Files\VideoLAN\VLC\libvlc.dll"
```

Để dùng chức năng ghép video, tải bản FFmpeg cho Windows rồi chọn một trong hai cách:

- Chép `ffmpeg.exe` và `ffprobe.exe` vào thư mục `bin` của dự án.
- Hoặc thêm thư mục chứa FFmpeg vào biến môi trường `PATH`.

Kiểm tra FFmpeg:

```powershell
ffmpeg -version
ffprobe -version
```

## Cấu hình

Ứng dụng đọc file `config.json` nằm cùng thư mục với `main.py` (hoặc cùng thư mục với file `.exe` sau khi đóng gói). Hai phần quan trọng là đường dẫn kho video và kết nối MySQL:

```json
{
  "storage_path": "D:/ATGRecorder/videos",
  "db": {
    "host": "127.0.0.1",
    "port": 3306,
    "database": "atg_order_system",
    "user": "atg_app",
    "password": "your_password",
    "charset": "utf8mb4",
    "connect_timeout": 5
  }
}
```

- `storage_path` (hoặc `play_path`/`video_path`) phải là thư mục có thật trên máy mới.
- Bảng MySQL `packing_videos` cần có các cột `order_code`, `file_path`, `camera_name`, `created_at`.
- Nếu `file_path` trong database là đường dẫn tương đối, ứng dụng sẽ ghép nó với `storage_path`.
- Tài khoản MySQL cần quyền `SELECT` trên bảng `packing_videos`.
- Không commit mật khẩu database, URL camera hoặc thông tin nội bộ lên repository công khai.

Ví dụ cấp quyền MySQL (thay tài khoản và mật khẩu cho phù hợp):

```sql
CREATE USER 'atg_app'@'localhost' IDENTIFIED BY 'your_password';
GRANT SELECT ON atg_order_system.packing_videos TO 'atg_app'@'localhost';
FLUSH PRIVILEGES;
```

Nếu MySQL nằm trên máy khác, thay `localhost` bằng host được phép kết nối và bảo đảm firewall đã mở cổng MySQL trong mạng nội bộ.

## Chạy ứng dụng

```powershell
.\.venv\Scripts\Activate.ps1
python main.py
```

Khi chạy, ứng dụng tải tối đa 10.000 bản ghi video mới nhất và làm mới danh sách từ database mỗi 5 giây. Các định dạng được hỗ trợ: `.mp4`, `.mkv`, `.avi`, `.mov`, `.ts`.

## Ghép video theo đơn hàng

1. Chọn một mã đơn hàng.
2. Tích từ 2 đến 4 video trong danh sách.
3. Chọn bố cục `Tự động`, `Ngang`, `Dọc` hoặc `Lưới 2x2`.
4. Bấm **Ghép video đã chọn** và chọn nơi lưu file MP4.
5. Theo dõi tiến trình hoặc bấm **Huỷ ghép** khi cần.

Ở chế độ `Tự động`, hai video được ưu tiên xếp dọc: video thứ nhất ở
trên và video thứ hai ở dưới. Với 3–4 video, ứng dụng dùng lưới 2x2.
Lựa chọn `Ngang` vẫn có thể được sử dụng khi cần xếp các video trên cùng một hàng.

Video kết quả dùng H.264, âm thanh AAC từ camera đầu tiên có audio và kết thúc theo video ngắn nhất. Ứng dụng không sửa, di chuyển hay xoá video nguồn và không ghi kết quả vào database. Log tác vụ nằm tại `logs/multiplay_merge.log`.

## Đóng gói file EXE

Dự án đã có file cấu hình PyInstaller. Sau khi cài dependencies, chạy:

```powershell
.\build_onefile.ps1
```

Script tạo một file duy nhất tại `dist/ATG-MultiPlay.exe` và tự đóng gói
`bin/ffmpeg.exe`, `bin/ffprobe.exe` nếu có. Nếu PowerShell chặn script:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\build_onefile.ps1
```

Để đóng gói kèm FFmpeg/ffprobe mà không sửa file `.spec`:

```powershell
pyinstaller --noconfirm --onefile --windowed --name "ATG-MultiPlay" `
  --icon=icon.ico --add-data "icon.ico;." --add-data "antn.png;." `
  --add-binary "bin/ffmpeg.exe;bin" --add-binary "bin/ffprobe.exe;bin" main.py
```

File kết quả nằm trong thư mục `dist`. Khi chuyển sang máy khác, đặt `config.json` cạnh file `.exe`. Máy đích vẫn cần VLC; hoặc có thể chép toàn bộ thư mục VLC vào `bin/vlc` cạnh file `.exe`.

## Chạy kiểm thử

```powershell
python -m unittest discover -s tests -v
```

## Lỗi thường gặp

### `Không tìm thấy VLC`

Cài VLC đúng phiên bản 64-bit hoặc chép thư mục cài VLC vào `bin/vlc`. Kiểm tra trong thư mục đó phải có `libvlc.dll` và thư mục `plugins`.

### Không thấy mã đơn hàng/video

- Kiểm tra `storage_path` có tồn tại.
- Kiểm tra thông tin MySQL trong `config.json`.
- Kiểm tra đường dẫn trong cột `file_path` trỏ tới file video có thật.
- Thử đăng nhập MySQL bằng cùng tài khoản và chạy truy vấn trên bảng `packing_videos`.

### `ModuleNotFoundError`

Đảm bảo môi trường ảo đã được kích hoạt và chạy lại:

```powershell
pip install -r requirements.txt
```

## Cấu trúc chính

```text
MULTIPLAY/
├── core/                  # Database, cấu hình, index, đồng bộ và luồng video
├── ui/                    # Cửa sổ chính và trình phát VLC/FFmpeg
├── main.py                # Điểm khởi chạy ứng dụng
├── config.json            # Cấu hình máy chạy (không nên chứa secret thật khi public)
├── ATG-MultiPlay.spec     # Cấu hình đóng gói PyInstaller
├── requirements.txt       # Dependencies Python
└── README.md
```
