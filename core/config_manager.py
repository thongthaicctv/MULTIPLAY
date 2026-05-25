import os
import sys
import json


class ConfigManager:

    def __init__(self):

        if getattr(sys, "frozen", False):
            self.base_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

        self.config_file = os.path.join(self.base_dir, "config.json")

    def load_config(self):

        if not os.path.exists(self.config_file):
            print("CONFIG NOT FOUND:", self.config_file)
            return {}

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print("LOAD CONFIG ERROR:", e)
            return {}

    def load_folder(self):

        data = self.load_config()

        folder = (
            data.get("play_path")
            or data.get("storage_path")
            or data.get("video_path")
            or ""
        )

        folder = os.path.expandvars(os.path.expanduser(str(folder).strip()))

        if not folder:
            return None

        if not os.path.isabs(folder):
            folder = os.path.join(self.base_dir, folder)

        folder = os.path.abspath(folder)

        if os.path.exists(folder):
            return folder

        return None

    def load_database_config(self):

        data = self.load_config()

        db = data.get(
            "db",
            {}
        )

        return {

            "host": db.get(
                "host",
                "127.0.0.1"
            ),

            "port": int(
                db.get(
                    "port",
                    3306
                )
            ),

            "database": db.get(
                "database",
                "atg_order_system"
            ),

            "user": db.get(
                "user",
                "atg_app"
            ),

            "password": db.get(
                "password",
                ""
            ),

            "charset": db.get(
                "charset",
                "utf8mb4"
            ),

            "connect_timeout": int(
                db.get(
                    "connect_timeout",
                    5
                )
            )
        }

    def save_folder(self, path):
        pass
