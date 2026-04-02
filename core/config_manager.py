import os
import json

CONFIG_DIR = r"C:\ProgramData\ATGMultiPlay"
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


class ConfigManager:

    def save_folder(self, path):

        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR)

        data = {
            "video_folder": path
        }

        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f)

    def load_folder(self):

        if not os.path.exists(CONFIG_FILE):
            return None

        try:
            with open(CONFIG_FILE) as f:
                data = json.load(f)

            return data.get("video_folder")

        except:
            return None