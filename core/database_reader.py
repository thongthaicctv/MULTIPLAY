import os
import threading
import time

import pymysql

from core.video_path_resolver import (
    RemoteVideoResolver,
    clean_path_value,
    is_network_path,
    log_detail,
)


# ===== MULTIPLAY-STORAGE-1B =====
# Resolver NAS dùng chung giữa các lần refresh (DatabaseReader được tạo mới mỗi 5s),
# để cache kết quả và worker nền tồn tại suốt vòng đời app.
_REMOTE_RESOLVER = None
_REMOTE_RESOLVER_LOCK = threading.Lock()

_ROOTS_CACHE_SECONDS = 60.0
_ROOTS_STATE = {"loaded_at": -1e9, "roots": [], "db": None, "storage_root": None}
_LOG_STATE = {"summary": None, "local_miss": set()}  # chống log lặp mỗi 5 giây


def _get_remote_resolver():
    global _REMOTE_RESOLVER
    with _REMOTE_RESOLVER_LOCK:
        if _REMOTE_RESOLVER is None:
            # not_found được thử lại sau 5 phút; NAS offline được thử lại sau 60 giây
            _REMOTE_RESOLVER = RemoteVideoResolver(
                _storage_roots,
                retry_seconds=300.0,
                offline_backoff=60.0,
            )
        return _REMOTE_RESOLVER


def _storage_roots():
    """[(storage_code, base_path)] từ storage_locations + storage_path config.

    Chạy trên worker nền (không phải UI thread). Cache 60 giây.
    """
    now = time.monotonic()
    state = _ROOTS_STATE
    if now - state["loaded_at"] < _ROOTS_CACHE_SECONDS:
        return state["roots"]

    roots = []
    db = state["db"]
    if db:
        try:
            conn = DatabaseReader(db).connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT storage_code, base_path
                        FROM storage_locations
                        WHERE base_path IS NOT NULL
                          AND base_path <> ''
                        ORDER BY storage_code ASC
                        """
                    )
                    for row in cur.fetchall():
                        code = clean_path_value(row.get("storage_code"))
                        base = clean_path_value(row.get("base_path"))
                        if base:
                            roots.append((code, base))
            finally:
                conn.close()
        except Exception as e:
            print("[STORAGE] storage_locations unavailable:", type(e).__name__, flush=True)

    storage_root = state["storage_root"]
    if storage_root:
        roots.append(("CONFIG", storage_root))

    state["roots"] = roots
    state["loaded_at"] = now
    return roots


class DatabaseReader:

    VIDEO_EXTS = (".mp4", ".mkv", ".avi", ".mov", ".ts")

    SQL_WITH_STORAGE = """
        SELECT
            id,
            order_code,
            file_path,
            relative_path,
            storage_code,
            file_name,
            camera_name,
            created_at
        FROM packing_videos
        WHERE file_path IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 10000
        """

    SQL_LEGACY = """
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

    def _fetch_rows(self):
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                try:
                    cur.execute(self.SQL_WITH_STORAGE)
                except pymysql.err.OperationalError as e:
                    # 1054 = Unknown column -> DB chưa có cột storage, dùng query cũ
                    if not e.args or e.args[0] != 1054:
                        raise
                    print("[STORAGE] storage columns not found, using legacy query", flush=True)
                    cur.execute(self.SQL_LEGACY)
                return cur.fetchall()
        finally:
            conn.close()

    def load_video_index(self):

        result = {}

        try:
            rows = self._fetch_rows()

            print("MYSQL VIDEOS:", len(rows))

            _ROOTS_STATE["db"] = self.db
            _ROOTS_STATE["storage_root"] = self.storage_root
            resolver = _get_remote_resolver()
            counts = {"local": 0, "nas": 0, "pending": 0, "not_found": 0}

            for row in rows:
                order = str(row.get("order_code", "")).strip()
                raw_path = str(row.get("file_path", "") or "").strip()

                if not order:
                    continue

                if not raw_path:
                    continue

                name_for_ext = (
                    clean_path_value(row.get("relative_path"))
                    or clean_path_value(row.get("file_name"))
                    or raw_path
                )
                if not (raw_path.lower().endswith(self.VIDEO_EXTS)
                        or name_for_ext.lower().endswith(self.VIDEO_EXTS)):
                    continue

                path = self.resolve_video_path(raw_path)

                # A. LOCAL: kiểm tra đồng bộ như trước (bỏ qua đường dẫn mạng)
                if path and not is_network_path(path) and os.path.exists(path):
                    counts["local"] += 1
                    hit_key = ("local", order, path)
                    if hit_key not in _LOG_STATE["local_miss"]:
                        _LOG_STATE["local_miss"].add(hit_key)
                        log_detail("LOCAL HIT", f"order={order} path={path}")
                    self._add(result, order, path)
                    continue

                # B/C. STORAGE/NAS: chỉ đọc cache, I/O mạng chạy nền
                key = (order, raw_path)
                if key not in _LOG_STATE["local_miss"]:
                    _LOG_STATE["local_miss"].add(key)
                    log_detail("LOCAL MISS", f"order={order} file={os.path.basename(raw_path.replace(chr(92), '/'))}")

                status, remote_path = resolver.lookup(row)
                if status == "hit":
                    counts["nas"] += 1
                    self._add(result, order, remote_path)
                    continue

                if status == "pending":
                    resolver.submit(row)
                    counts["pending"] += 1
                else:
                    counts["not_found"] += 1

            summary = (counts["local"], counts["nas"], counts["pending"], counts["not_found"])
            if summary != _LOG_STATE["summary"]:
                _LOG_STATE["summary"] = summary
                print(
                    "[STORAGE] index: local={} nas={} pending={} not_found={}".format(*summary),
                    flush=True,
                )

            return result

        except Exception as e:
            print("MYSQL VIDEO ERROR:", e)
            return {}

    @staticmethod
    def _add(result, order, path):
        result.setdefault(order, [])
        if path not in result[order]:
            result[order].append(path)

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
