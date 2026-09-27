"""Resolve đường dẫn video của MultiPlay theo LOCAL trước, sau đó STORAGE/NAS.

Nguyên tắc (MULTIPLAY-STORAGE-1B):
- Chỉ đọc: không ghi DB, không ghi/xoá file, không quét thư mục (không os.walk).
- LOCAL được kiểm tra đồng bộ (rẻ, giữ nguyên hành vi cũ).
- Mọi truy cập đường dẫn mạng (UNC/NAS) chỉ chạy trên worker thread nền,
  có kiểm tra root online với timeout, cache kết quả và backoff khi NAS offline.
  => UI thread không bao giờ bị chặn bởi NAS chậm/offline.
- Không hard-code NAS: root lấy từ bảng storage_locations và storage_path config.
"""

from __future__ import annotations

import os
import queue
import threading
import time
from typing import Callable, Iterable

LOG_PREFIX = "[STORAGE]"


def _log(message: str) -> None:
    print(f"{LOG_PREFIX} {message}", flush=True)


# Giới hạn log chi tiết theo từng loại để không spam console khi có hàng nghìn record.
# Đặt biến môi trường ATG_STORAGE_LOG_LIMIT=0 để log không giới hạn.
try:
    _DETAIL_LIMIT = int(os.environ.get("ATG_STORAGE_LOG_LIMIT", "50"))
except ValueError:
    _DETAIL_LIMIT = 50
_DETAIL_COUNTS = {}
_DETAIL_LOCK = threading.Lock()


def log_detail(category: str, message: str) -> None:
    with _DETAIL_LOCK:
        count = _DETAIL_COUNTS.get(category, 0) + 1
        _DETAIL_COUNTS[category] = count
    if _DETAIL_LIMIT <= 0 or count <= _DETAIL_LIMIT:
        _log(f"{category}: {message}")
    elif count == _DETAIL_LIMIT + 1:
        _log(f"{category}: ... (đã đạt giới hạn {_DETAIL_LIMIT} dòng, xem dòng [STORAGE] index để biết tổng)")


def clean_path_value(value) -> str:
    return str(value or "").strip().strip('"').strip()


def is_network_path(path: str) -> bool:
    value = str(path or "")
    return value.startswith("\\\\") or value.startswith("//")


def split_path_parts(path: str) -> list[str]:
    """Tách đường dẫn Windows/Posix thành các phần, bỏ ổ đĩa và phần rỗng."""
    value = clean_path_value(path).replace("\\", "/")
    parts = [part for part in value.split("/") if part]
    if parts and len(parts[0]) == 2 and parts[0][1] == ":":
        parts = parts[1:]
    return parts


def join_under_root(root: str, relative: str) -> str:
    root = clean_path_value(root)
    rel_parts = split_path_parts(relative)
    if not root or not rel_parts:
        return ""
    sep = "\\" if (is_network_path(root) or "\\" in root or (len(root) >= 2 and root[1] == ":")) else os.sep
    return root.rstrip("\\/") + sep + sep.join(rel_parts)


def legacy_relative_candidates(file_path: str) -> list[str]:
    """Phần đuôi hợp lý của file_path cũ, ưu tiên dạng <ngày>\\<file>.

    Không dùng wildcard/scan: mỗi ứng viên là MỘT đường dẫn cụ thể nên không thể
    chọn nhầm file cùng tên ở ngày khác.
    """
    parts = split_path_parts(file_path)
    result = []
    if len(parts) >= 2:
        result.append("/".join(parts[-2:]))
    if len(parts) >= 3:
        result.append("/".join(parts[-3:]))
    return result


def _dedupe(values: Iterable[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if not value:
            continue
        key = value.replace("/", "\\").lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def build_candidates(record: dict, roots: list[tuple[str, str]]) -> list[str]:
    """Danh sách ứng viên theo thứ tự ưu tiên.

    roots: [(storage_code, base_path), ...]
    Thứ tự:
      1. root của đúng storage_code + relative_path
      2. các root khác + relative_path
      3. root + phần đuôi file_path cũ (<ngày>\\<file>, rồi 3 cấp)
      4. root + file_name
    """
    storage_code = clean_path_value(record.get("storage_code"))
    relative_path = clean_path_value(record.get("relative_path"))
    file_path = clean_path_value(record.get("file_path"))
    file_name = clean_path_value(record.get("file_name")) or (split_path_parts(file_path) or [""])[-1]

    preferred = [base for code, base in roots if storage_code and code == storage_code]
    others = [base for code, base in roots if not (storage_code and code == storage_code)]
    ordered_roots = _dedupe(preferred + others)

    candidates = []
    if relative_path:
        candidates += [join_under_root(root, relative_path) for root in ordered_roots]
    for tail in legacy_relative_candidates(file_path):
        candidates += [join_under_root(root, tail) for root in ordered_roots]
    if file_name:
        candidates += [join_under_root(root, file_name) for root in ordered_roots]
    return _dedupe(candidates)


def root_of_candidate(candidate: str, roots: list[tuple[str, str]]) -> tuple[str, str]:
    norm = candidate.replace("/", "\\").lower()
    for code, base in roots:
        base_norm = clean_path_value(base).replace("/", "\\").rstrip("\\").lower()
        if base_norm and norm.startswith(base_norm + "\\"):
            return code, base
    return "", ""


def record_key(record: dict) -> tuple:
    return (
        str(record.get("id") or ""),
        clean_path_value(record.get("file_path")),
        clean_path_value(record.get("relative_path")),
        clean_path_value(record.get("storage_code")),
    )


class RemoteVideoResolver:
    """Resolver nền cho video không còn ở LOCAL.

    - lookup(record): chỉ đọc cache, KHÔNG I/O -> an toàn trên UI thread.
    - submit(record): đưa vào hàng đợi nền (không chặn).
    - resolve_now(record): resolve đồng bộ (dùng cho worker và test).
    """

    def __init__(
        self,
        roots_provider: Callable[[], list[tuple[str, str]]],
        exists: Callable[[str], bool] = os.path.isfile,
        root_online: Callable[[str], bool] = os.path.isdir,
        probe_timeout: float = 2.0,
        retry_seconds: float = 60.0,
        offline_backoff: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
        start_worker: bool = True,
    ):
        self._roots_provider = roots_provider
        self._exists = exists
        self._root_online = root_online
        self._probe_timeout = probe_timeout
        self._retry_seconds = retry_seconds
        self._offline_backoff = offline_backoff
        self._clock = clock

        self._lock = threading.Lock()
        self._results = {}        # key -> (path|None, checked_at)
        self._pending = set()
        self._logged_not_found = set()
        self._root_state = {}     # base_path_lower -> (online, checked_at)
        self._queue = queue.Queue()
        self._worker = None
        if start_worker:
            self._worker = threading.Thread(target=self._run, name="MultiPlayStorageResolver", daemon=True)
            self._worker.start()

    # ---------- non-blocking API (UI thread) ----------
    def lookup(self, record: dict):
        """Trả về (status, path). status: 'hit' | 'not_found' | 'pending'."""
        key = record_key(record)
        with self._lock:
            cached = self._results.get(key)
        if cached is None:
            return "pending", None
        path, checked_at = cached
        if path:
            return "hit", path
        if self._clock() - checked_at >= self._retry_seconds:
            return "pending", None
        return "not_found", None

    def submit(self, record: dict) -> None:
        key = record_key(record)
        with self._lock:
            if key in self._pending:
                return
            cached = self._results.get(key)
            if cached is not None:
                path, checked_at = cached
                if path or self._clock() - checked_at < self._retry_seconds:
                    return
            self._pending.add(key)
        self._queue.put(dict(record))

    # ---------- blocking API (worker / tests) ----------
    def resolve_now(self, record: dict):
        key = record_key(record)
        try:
            roots = list(self._roots_provider() or [])
        except Exception as exc:  # không để lỗi DB làm chết worker
            _log(f"ROOTS ERROR: {type(exc).__name__}")
            roots = []

        order = record.get("order_code", "")
        name = clean_path_value(record.get("file_name")) or (split_path_parts(record.get("file_path")) or [""])[-1]

        # file_path tuyệt đối dạng UNC (không phải LOCAL) -> thử trực tiếp nếu root online
        direct = clean_path_value(record.get("file_path"))
        candidates = []
        if direct and is_network_path(direct):
            candidates.append(direct)
        candidates += build_candidates(record, roots)

        deferred = False
        for candidate in candidates:
            code, base = root_of_candidate(candidate, roots)
            probe_base = base or (candidate if not is_network_path(candidate) else _unc_share_root(candidate))
            if probe_base and is_network_path(probe_base) and not self._is_root_online(probe_base):
                deferred = True
                continue
            try:
                if self._exists(candidate):
                    self._store(key, candidate)
                    log_detail("NAS HIT", f"storage={code or '-'} order={order} path={candidate}")
                    return candidate
            except OSError:
                continue

        if deferred:
            # NAS offline: không ghi negative cache dài hạn, thử lại sau backoff
            self._store(key, None, checked_at=self._clock() - self._retry_seconds + self._offline_backoff)
            log_detail("NAS DEFERRED", f"order={order} file={name} (root offline)")
            return None

        self._store(key, None)
        with self._lock:
            first = key not in self._logged_not_found
            self._logged_not_found.add(key)
        if first:
            log_detail("NOT FOUND", f"order={order} file={name} candidates={len(candidates)}")
        return None

    def wait_idle(self, timeout: float = 5.0) -> bool:
        """Chờ hàng đợi nền rỗng (dùng cho test)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                busy = bool(self._pending)
            if not busy and self._queue.empty():
                return True
            time.sleep(0.01)
        return False

    # ---------- internals ----------
    def _store(self, key, path, checked_at=None):
        with self._lock:
            self._results[key] = (path, self._clock() if checked_at is None else checked_at)

    def _run(self):
        while True:
            record = self._queue.get()
            try:
                self.resolve_now(record)
            except Exception as exc:
                _log(f"RESOLVE ERROR: {type(exc).__name__}")
            finally:
                with self._lock:
                    self._pending.discard(record_key(record))

    def _is_root_online(self, base: str) -> bool:
        key = base.replace("/", "\\").rstrip("\\").lower()
        now = self._clock()
        with self._lock:
            state = self._root_state.get(key)
        if state is not None and now - state[1] < self._offline_backoff:
            return state[0]

        result = {"online": False}

        def probe():
            try:
                result["online"] = bool(self._root_online(base))
            except OSError:
                result["online"] = False

        thread = threading.Thread(target=probe, name="MultiPlayStorageProbe", daemon=True)
        thread.start()
        thread.join(self._probe_timeout)
        online = (not thread.is_alive()) and result["online"]

        with self._lock:
            previous = self._root_state.get(key)
            self._root_state[key] = (online, self._clock())
        if previous is None or previous[0] != online:
            _log(f"ROOT {'ONLINE' if online else 'OFFLINE'}: {base}")
        return online


def _unc_share_root(path: str) -> str:
    parts = split_path_parts(path)
    if len(parts) >= 2:
        return "\\\\" + parts[0] + "\\" + parts[1]
    return ""
