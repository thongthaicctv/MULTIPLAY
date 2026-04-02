import json
import os
import base64
import hashlib
import requests

from datetime import datetime, timedelta
from core.hardware_id import get_machine_id


SECRET = "ATG_LICENSE_SECRET_2026"

SHEET_URL = "https://opensheet.elk.sh/1wv0-rsNmf7dXBmnG7fn6c6ZnhE18wuZP8mobGrlslR0/LICENSE"

CACHE_DIR = r"C:\ProgramData\ATGMultiPlay"
CACHE_FILE = os.path.join(CACHE_DIR, "license_cache.dat")

OFFLINE_GRACE = 5


class LicenseManager:

    # ================= UTIL =================

    def _encode(self, data):

        raw = json.dumps(data)

        sign = hashlib.sha256((raw + SECRET).encode()).hexdigest()

        pack = {
            "payload": raw,
            "sign": sign
        }

        return base64.b64encode(json.dumps(pack).encode()).decode()

    def _decode(self, text):

        try:
            pack = json.loads(base64.b64decode(text).decode())

            raw = pack["payload"]
            sign = pack["sign"]

            check = hashlib.sha256((raw + SECRET).encode()).hexdigest()

            if check != sign:
                return None

            return json.loads(raw)

        except:
            return None

    def _save_cache(self, data):

        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)

        enc = self._encode(data)

        with open(CACHE_FILE, "w") as f:
            f.write(enc)

    def _load_cache(self):

        if not os.path.exists(CACHE_FILE):
            return None

        with open(CACHE_FILE) as f:
            enc = f.read()

        return self._decode(enc)

    # ================= VERIFY =================

    def verify(self):

        machine = get_machine_id()

        # ===== TRY ONLINE =====
        try:
            data = requests.get(SHEET_URL, timeout=5).json()

            for row in data:

                if row["machine_id"] == machine:

                    if row["status"] != "ACTIVE":

                        # ⭐ XÓA CACHE NGAY
                        if os.path.exists(CACHE_FILE):
                            os.remove(CACHE_FILE)

                        return False, "License disabled"

                    expire = datetime.strptime(
                        row["expire_date"], "%Y-%m-%d"
                    )

                    if datetime.now() > expire:
                        return False, "License expired"

                    cache = {
                        "machine": machine,
                        "expire": row["expire_date"],
                        "last_sync": datetime.now().isoformat()
                    }

                    self._save_cache(cache)

                    return True, "ONLINE OK"

            # machine không còn trong sheet
            if os.path.exists(CACHE_FILE):
                os.remove(CACHE_FILE)

            return False, "Machine not activated"

        # ===== OFFLINE =====
        except:

            cache = self._load_cache()

            if not cache:
                return False, "No internet and no cache"

            if cache["machine"] != machine:
                return False, "Cache invalid"

            expire = datetime.strptime(cache["expire"], "%Y-%m-%d")

            if datetime.now() > expire:
                return False, "License expired"

            last = datetime.fromisoformat(cache["last_sync"])

            if datetime.now() - last > timedelta(days=OFFLINE_GRACE):
                return False, "Offline too long"

            return True, "OFFLINE OK"