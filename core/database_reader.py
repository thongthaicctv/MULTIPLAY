import os

import pymysql


class DatabaseReader:

    VIDEO_EXTS = (".mp4", ".mkv", ".avi", ".mov", ".ts")

    def __init__(self, db_config, storage_root=None):
        self.db = db_config
        self.storage_root = storage_root

    def connect(self):

        return pymysql.connect(
            host=self.db.get("host"),
            port=int(self.db.get("port", 3306)),
            user=self.db.get("user"),
            password=self.db.get("password"),
            database=self.db.get("database"),
            charset=self.db.get("charset", "utf8mb4"),
            connect_timeout=int(self.db.get("connect_timeout", 5)),
            cursorclass=pymysql.cursors.DictCursor
        )

    def load_video_index(self):

        result = {}

        sql = """
        SELECT
            order_code,
            file_path,
            camera_name,
            created_at
        FROM packing_videos
        WHERE file_path IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 10000
        """

        try:
            conn = self.connect()

            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()

            conn.close()

            print("MYSQL VIDEOS:", len(rows))

            for row in rows:
                order = str(row.get("order_code", "")).strip()
                raw_path = str(row.get("file_path", "")).strip()
                path = self.resolve_video_path(raw_path)

                if not order:
                    continue

                if not path:
                    continue

                if not path.lower().endswith(self.VIDEO_EXTS):
                    continue

                if not os.path.exists(path):
                    continue

                result.setdefault(order, [])

                if path not in result[order]:
                    result[order].append(path)

            return result

        except Exception as e:
            print("MYSQL VIDEO ERROR:", e)
            return {}

    def resolve_video_path(self, path):

        if not path:
            return ""

        path = os.path.expandvars(os.path.expanduser(str(path).strip()))
        path = path.replace("/", os.sep)

        if os.path.isabs(path):
            return os.path.abspath(path)

        if not self.storage_root:
            return os.path.abspath(path)

        return os.path.abspath(os.path.join(self.storage_root, path))
