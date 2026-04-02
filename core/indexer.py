import os
import json

from core.index_builder import IndexBuilder


class Indexer:

    def __init__(self, root):
        self.root = root

    def load(self):

        print("🔥 ALWAYS BUILD INDEX FROM index.json")

        # ===== BUILD (convert từ index.json) =====
        builder = IndexBuilder(self.root)
        ok = builder.build()

        if not ok:
            print("❌ BUILD INDEX FAIL")
            return {}

        # ===== LOAD video_index.json =====
        index_file = os.path.join(self.root, "video_index.json")

        if not os.path.exists(index_file):
            print("❌ KHÔNG TẠO ĐƯỢC video_index.json")
            return {}

        print("✅ LOAD INDEX:", index_file)

        with open(index_file, encoding="utf-8") as f:
            data = json.load(f)

        result = {}

        for order, files in data.items():

            order = str(order).strip()

            if not order:
                continue

            abs_files = []

            for f in files:

                # chỉ lấy mkv (an toàn thêm 1 lớp)
                if not f.lower().endswith(".mkv"):
                    continue

                full_path = os.path.join(self.root, f)

                abs_files.append(full_path)

            if abs_files:
                result[order] = abs_files

        print("✅ TOTAL ORDERS:", len(result))

        return result