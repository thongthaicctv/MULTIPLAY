# ATG-MultiPlay PATCH - index mở được MP4 + MKV

Thay đè 5 file trong source cũ:

- core/index_builder.py
- core/indexer.py
- core/index_importer.py
- ui/main_window.py
- ui/player_vlc_widget.py

Chức năng đã sửa:

- Đọc chuẩn mới: <thư mục video>/index/YYYY-MM-DD.json
- Fallback chuẩn cũ: <thư mục video>/index.json
- Tạo lại: <thư mục video>/video_index.json
- Hỗ trợ mở: .mp4, .mkv, .avi, .mov, .ts
- Chỉ đưa vào danh sách những file video thật sự tồn tại
- Lưu đường dẫn tương đối để copy thư mục sang máy khác vẫn mở được

Cách dùng:

1. Giải nén patch.
2. Copy 5 file vào đúng thư mục source ATG-MultiPlay.
3. Chạy lại main.py.
4. Chọn thư mục gốc chứa video, ví dụ:
   D:/Video 2
5. Không chọn thư mục index, phải chọn thư mục cha chứa:
   index/
   2026-05-08/
   2026-05-10/
