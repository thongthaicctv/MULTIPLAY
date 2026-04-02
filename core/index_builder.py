import os
import json


class IndexBuilder:

    def __init__(self, root):
        self.root = root
        self.result = {}

    def build(self):

        src = os.path.join(self.root, "index.json")
        dst = os.path.join(self.root, "video_index.json")

        if not os.path.exists(src):
            print("❌ KHÔNG CÓ index.json")
            return False

        print("🔥 BUILD FROM index.json (NO SCAN)")

        with open(src, "r", encoding="utf-8") as f:
            raw = json.load(f)

        result = {}

        for key, item in raw.items():

            videos = item.get("videos", {})
            files = []

            for cam, path in videos.items():

                if not path:
                    continue

                if not path.lower().endswith(".mkv"):
                    continue

                path = path.replace("\\", "/")
                files.append(path)

            if files:
                result[key.strip()] = files

        # 🔥 overwrite luôn
        with open(dst, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)

        print(f"✅ BUILD DONE: {len(result)} orders")

        return True