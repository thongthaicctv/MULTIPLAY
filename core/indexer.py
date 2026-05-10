import os
import json

from core.index_builder import IndexBuilder


class Indexer:

    VIDEO_EXTS = (".mp4", ".mkv", ".avi", ".mov")

    def __init__(self, root):
        self.root = root

    def load(self):
        print("🔥 LOAD INDEX FROM NEW INDEX FOLDER")

        builder = IndexBuilder(self.root)
        ok = builder.build()

        if not ok:
            print("❌ BUILD INDEX FAIL")
            return {}

        index_file = os.path.join(self.root, "video_index.json")

        if not os.path.exists(index_file):
            print("❌ KHÔNG TẠO ĐƯỢC video_index.json")
            return {}

        print("✅ LOAD INDEX:", index_file)

        try:
            with open(index_file, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print("❌ LỖI ĐỌC video_index.json:", e)
            return {}

        result = {}

        for order, files in data.items():
            order = str(order).strip()

            if not order:
                continue

            abs_files = []

            for f in files:
                if not str(f).lower().endswith(self.VIDEO_EXTS):
                    continue

                full_path = os.path.join(self.root, str(f).replace("/", os.sep))

                if os.path.exists(full_path):
                    abs_files.append(full_path)
                else:
                    print("⚠️ FILE VIDEO KHÔNG TỒN TẠI:", full_path)

            if abs_files:
                result[order] = abs_files

        print("✅ TOTAL ORDERS:", len(result))
        return result
