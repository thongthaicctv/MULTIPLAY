import os
import json


class IndexBuilder:
    """
    Build video_index.json cho ATG-MultiPlay từ chuẩn index mới của ATG Recorder.

    Hỗ trợ MP4 + MKV + AVI + MOV + TS.

    Hỗ trợ:
    1) Chuẩn mới:
       <root>/index/YYYY-MM-DD.json

    2) Chuẩn cũ dự phòng:
       <root>/index.json

    Output:
       <root>/video_index.json

    Dạng output:
       {
           "MA_DON": [
               "2026-05-10/video_1.mp4",
               "2026-05-10/video_2.mkv"
           ]
       }
    """

    VIDEO_EXTS = (".mp4", ".mkv", ".avi", ".mov", ".ts")

    def __init__(self, root):
        self.root = root

    def build(self):
        result = {}

        # Ưu tiên chuẩn mới: root/index/*.json
        ok = self._build_from_index_folder(result)

        # Nếu không có dữ liệu thì fallback chuẩn cũ: root/index.json
        if not ok:
            ok = self._build_from_old_index_json(result)

        if not ok:
            print("❌ KHÔNG TÌM THẤY INDEX HỢP LỆ")
            print("   Cần có: <thư mục video>/index/YYYY-MM-DD.json")
            print("   hoặc:   <thư mục video>/index.json")
            return False

        dst = os.path.join(self.root, "video_index.json")

        with open(dst, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"✅ BUILD DONE: {len(result)} mã đơn")
        print(f"✅ VIDEO INDEX: {dst}")
        return True

    def _add_video(self, result, order_code, rel_path):
        if not order_code:
            return

        if not rel_path:
            return

        rel_path = str(rel_path).replace("\\", "/").strip()

        if not rel_path.lower().endswith(self.VIDEO_EXTS):
            return

        # Không lưu path tuyệt đối vào video_index.json.
        # Luôn lưu path tương đối để khi copy cả thư mục sang máy khác vẫn mở được.
        rel_path = self._to_relative_path(rel_path)

        full_path = os.path.join(self.root, rel_path.replace("/", os.sep))

        # Chỉ đưa vào danh sách nếu file video thật sự tồn tại
        if not os.path.exists(full_path):
            print("⚠️ VIDEO KHÔNG TỒN TẠI:", full_path)
            return

        order_code = str(order_code).strip()

        if not order_code:
            return

        result.setdefault(order_code, [])

        if rel_path not in result[order_code]:
            result[order_code].append(rel_path)

    def _to_relative_path(self, path):
        path = str(path).replace("\\", "/").strip()

        root_norm = os.path.abspath(self.root).replace("\\", "/")

        # Nếu path là tuyệt đối nằm trong root thì đổi về tương đối
        if os.path.isabs(path):
            try:
                path = os.path.relpath(path, self.root).replace("\\", "/")
            except Exception:
                pass

        # Xử lý trường hợp lưu dạng D:/Video 2/2026-05-10/a.mp4
        if path.lower().startswith(root_norm.lower() + "/"):
            path = path[len(root_norm) + 1:]

        return path.lstrip("/")

    def _build_from_index_folder(self, result):
        index_dir = os.path.join(self.root, "index")

        if not os.path.isdir(index_dir):
            print("⚠️ Không có thư mục index:", index_dir)
            return False

        json_files = []

        for name in os.listdir(index_dir):
            if not name.lower().endswith(".json"):
                continue

            # bỏ qua file danh sách nếu sau này có tạo
            if name.lower() in ("index_list.json", "video_index.json"):
                continue

            json_files.append(os.path.join(index_dir, name))

        json_files.sort(reverse=True)

        if not json_files:
            print("⚠️ Thư mục index không có file .json")
            return False

        print("🔥 BUILD FROM index/*.json")
        print("✅ FOUND JSON:", len(json_files))

        for file in json_files:
            try:
                with open(file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
            except Exception as e:
                print("❌ LỖI ĐỌC JSON:", file, e)
                continue

            # Chuẩn mới:
            # {
            #   "videos": [
            #      {"order_code": "...", "file_path": "2026-05-10/abc.mp4"}
            #   ]
            # }
            videos = raw.get("videos", [])

            if isinstance(videos, list):
                for item in videos:
                    if not isinstance(item, dict):
                        continue

                    order_code = (
                        item.get("order_code")
                        or item.get("qr_code")
                        or item.get("order")
                        or item.get("code")
                    )

                    rel_path = (
                        item.get("file_path")
                        or item.get("path")
                        or item.get("filename")
                    )

                    # Nếu chỉ có filename thì ghép thêm ngày
                    if rel_path and "/" not in str(rel_path).replace("\\", "/"):
                        date = item.get("date") or raw.get("date")
                        if date:
                            rel_path = f"{date}/{rel_path}"

                    self._add_video(result, order_code, rel_path)

            # Dự phòng nếu videos là dict
            elif isinstance(videos, dict):
                for order_code, files in videos.items():
                    if isinstance(files, list):
                        for rel_path in files:
                            self._add_video(result, order_code, rel_path)
                    elif isinstance(files, str):
                        self._add_video(result, order_code, files)

        return bool(result)

    def _build_from_old_index_json(self, result):
        src = os.path.join(self.root, "index.json")

        if not os.path.exists(src):
            print("⚠️ Không có index.json cũ:", src)
            return False

        print("🔥 BUILD FROM index.json CŨ")

        try:
            with open(src, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:
            print("❌ LỖI ĐỌC index.json:", e)
            return False

        if not isinstance(raw, dict):
            return False

        for key, item in raw.items():
            if not isinstance(item, dict):
                continue

            videos = item.get("videos", {})

            if isinstance(videos, dict):
                for cam, path in videos.items():
                    self._add_video(result, key, path)

            elif isinstance(videos, list):
                for path in videos:
                    self._add_video(result, key, path)

        return bool(result)
