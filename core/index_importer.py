from core.index_importer import IndexImporter
import os
import json


class Indexer:

    def __init__(self, root):
        self.root = root

    def load(self):

        # 🔥 LUÔN CONVERT
        importer = IndexImporter(self.root)
        ok = importer.run()

        if not ok:
            print("❌ CONVERT FAIL")
            return {}

        index_file = os.path.join(self.root, "video_index.json")

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
                abs_files.append(os.path.join(self.root, f))

            result[order] = abs_files

        print("✅ TOTAL:", len(result))
        return result