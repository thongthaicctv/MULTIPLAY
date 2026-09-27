"""MULTIPLAY-STORAGE-1B: test resolver LOCAL -> STORAGE/NAS (không cần DB/NAS thật)."""

import os
import tempfile
import threading
import time
import unittest
from unittest import mock

try:
    import pymysql  # noqa: F401
except ImportError:  # môi trường test không có pymysql
    import sys
    import types

    fake = types.ModuleType("pymysql")
    fake.err = types.SimpleNamespace(OperationalError=Exception)
    fake.cursors = types.SimpleNamespace(DictCursor=object)
    fake.connect = lambda **kw: None
    sys.modules["pymysql"] = fake

from core import database_reader
from core.database_reader import DatabaseReader
from core.video_path_resolver import (
    RemoteVideoResolver,
    build_candidates,
    legacy_relative_candidates,
)

NAS = r"\\nas01\share"
ROOTS = [("NAS01", NAS)]


class FakeNas:
    """Giả lập NAS: tập đường dẫn tồn tại + ghi lại mọi lần exists()."""

    def __init__(self, files=(), online=True, hang=0.0):
        self.files = {f.lower() for f in files}
        self.online = online
        self.hang = hang
        self.exists_calls = []
        self.exists_threads = set()

    def exists(self, path):
        self.exists_calls.append(path)
        self.exists_threads.add(threading.current_thread().name)
        return path.lower() in self.files

    def root_online(self, base):
        if self.hang:
            time.sleep(self.hang)
        return self.online


def make_resolver(nas, **kw):
    return RemoteVideoResolver(
        lambda: list(ROOTS),
        exists=nas.exists,
        root_online=nas.root_online,
        **kw,
    )


class ResolverUnitTests(unittest.TestCase):

    def test_candidates_priority_relative_then_legacy_then_name(self):
        rec = {
            "file_path": r"D:\VIDEO_DEBUG\2026-09-26\A_C2.ts",
            "relative_path": r"2026-09-26\A_C2.ts",
            "storage_code": "NAS01",
            "file_name": "A_C2.ts",
        }
        cands = build_candidates(rec, ROOTS)
        self.assertEqual(cands[0], NAS + r"\2026-09-26\A_C2.ts")
        self.assertIn(NAS + r"\VIDEO_DEBUG\2026-09-26\A_C2.ts", cands)
        self.assertEqual(cands[-1], NAS + r"\A_C2.ts")

    def test_legacy_tail_drops_drive(self):
        self.assertEqual(
            legacy_relative_candidates(r"D:\VIDEO_DEBUG\2026-09-24\x.ts"),
            ["2026-09-24/x.ts", "VIDEO_DEBUG/2026-09-24/x.ts"],
        )

    def test_same_name_other_date_is_not_picked(self):
        nas = FakeNas(files=[NAS + r"\2026-09-25\A_C2.ts"])  # sai ngày
        r = make_resolver(nas, start_worker=False)
        rec = {"file_path": r"D:\VIDEO_DEBUG\2026-09-26\A_C2.ts", "order_code": "A"}
        self.assertIsNone(r.resolve_now(rec))


class DatabaseReaderStorageTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.local_root = self.tmp.name
        day = os.path.join(self.local_root, "2026-09-26")
        os.makedirs(day)
        self.local_files = {}
        for cam in ("C1", "C4"):
            p = os.path.join(day, f"ORDA_{cam}.ts")
            open(p, "wb").close()
            self.local_files[cam] = p
        # reset trạng thái module
        database_reader._REMOTE_RESOLVER = None
        database_reader._LOG_STATE["summary"] = None
        database_reader._LOG_STATE["local_miss"] = set()

    def tearDown(self):
        database_reader._REMOTE_RESOLVER = None
        self.tmp.cleanup()

    def _row(self, cam, local=True, rel=True, code=True, order="ORDA", vid=None):
        name = f"{order}_{cam}.ts"
        file_path = (self.local_files[cam] if local and cam in self.local_files
                     else rf"D:\VIDEO_DEBUG\2026-09-26\{name}")
        return {
            "id": vid or hash((order, cam)) & 0xFFFF,
            "order_code": order,
            "file_path": file_path,
            "relative_path": rf"2026-09-26\{name}" if rel else None,
            "storage_code": "NAS01" if code else None,
            "file_name": name if rel else None,
            "camera_name": cam,
        }

    def _load(self, rows, nas, **kw):
        database_reader._REMOTE_RESOLVER = make_resolver(nas, **kw)
        reader = DatabaseReader({"host": "x"}, self.local_root)
        with mock.patch.object(DatabaseReader, "_fetch_rows", return_value=rows):
            return reader.load_video_index()

    def _load_until_stable(self, rows, nas, **kw):
        self._load(rows, nas, **kw)
        database_reader._REMOTE_RESOLVER.wait_idle(5)
        resolver = database_reader._REMOTE_RESOLVER
        reader = DatabaseReader({"host": "x"}, self.local_root)
        with mock.patch.object(DatabaseReader, "_fetch_rows", return_value=rows):
            return reader.load_video_index(), resolver

    # CASE 1
    def test_case1_local_only_no_nas_access(self):
        nas = FakeNas()
        data = self._load([self._row("C1")], nas)
        self.assertEqual(data, {"ORDA": [self.local_files["C1"]]})
        database_reader._REMOTE_RESOLVER.wait_idle(2)
        self.assertEqual(nas.exists_calls, [])

    # CASE 2
    def test_case2_nas_only(self):
        nas = FakeNas(files=[NAS + r"\2026-09-26\ORDA_C2.ts"])
        rows = [self._row("C2", local=False)]
        first = self._load(rows, nas)
        self.assertEqual(first, {})  # lần đầu: đang resolve nền, không chặn
        data, _ = self._load_until_stable(rows, nas)
        self.assertEqual(data, {"ORDA": [NAS + r"\2026-09-26\ORDA_C2.ts"]})

    # CASE 3
    def test_case3_mixed_order_keeps_all_four(self):
        nas = FakeNas(files=[NAS + r"\2026-09-26\ORDA_C2.ts", NAS + r"\2026-09-26\ORDA_C3.ts"])
        rows = [self._row("C1"), self._row("C2", local=False),
                self._row("C3", local=False), self._row("C4")]
        data, _ = self._load_until_stable(rows, nas)
        self.assertEqual(data["ORDA"], [
            self.local_files["C1"],
            NAS + r"\2026-09-26\ORDA_C2.ts",
            NAS + r"\2026-09-26\ORDA_C3.ts",
            self.local_files["C4"],
        ])

    # CASE 4
    def test_case4_legacy_record_without_storage_metadata(self):
        nas = FakeNas(files=[NAS + r"\2026-09-26\ORDA_C2.ts"])
        rows = [self._row("C2", local=False, rel=False, code=False)]
        data, _ = self._load_until_stable(rows, nas)
        self.assertEqual(data, {"ORDA": [NAS + r"\2026-09-26\ORDA_C2.ts"]})

    # CASE 5
    def test_case5_missing_file_does_not_drop_others(self):
        nas = FakeNas(files=[NAS + r"\2026-09-26\ORDA_C2.ts"])
        rows = [self._row("C1"), self._row("C2", local=False), self._row("C3", local=False)]
        data, resolver = self._load_until_stable(rows, nas)
        self.assertEqual(data["ORDA"], [self.local_files["C1"], NAS + r"\2026-09-26\ORDA_C2.ts"])
        self.assertEqual(resolver.lookup(rows[2])[0], "not_found")

    # CASE 6
    def test_case6_nas_offline_local_ok_no_blocking_no_scan(self):
        nas = FakeNas(files=[NAS + r"\2026-09-26\ORDA_C2.ts"], online=False, hang=3.0)
        rows = [self._row("C1"), self._row("C2", local=False), self._row("C4")]
        rows += [self._row(f"X{i}", local=False, order=f"OLD{i}", vid=10000 + i) for i in range(2000)]

        real_exists = os.path.exists
        main_thread_unc = []

        def guarded_exists(p):
            if str(p).startswith("\\\\") and threading.current_thread() is threading.main_thread():
                main_thread_unc.append(p)
            return real_exists(p)

        def forbid(*a, **k):
            raise AssertionError("scan NAS bị cấm")

        with mock.patch("os.path.exists", guarded_exists), \
                mock.patch("os.walk", forbid), mock.patch("os.scandir", forbid), \
                mock.patch("os.listdir", forbid):
            t0 = time.monotonic()
            data = self._load(rows, nas, probe_timeout=0.2, offline_backoff=60.0)
            elapsed_first = time.monotonic() - t0
            t0 = time.monotonic()
            reader = DatabaseReader({"host": "x"}, self.local_root)
            with mock.patch.object(DatabaseReader, "_fetch_rows", return_value=rows):
                data = reader.load_video_index()
            elapsed_second = time.monotonic() - t0
            database_reader._REMOTE_RESOLVER.wait_idle(10)

        self.assertEqual(data["ORDA"], [self.local_files["C1"], self.local_files["C4"]])
        self.assertLess(elapsed_first, 1.0)
        self.assertLess(elapsed_second, 1.0)
        self.assertEqual(main_thread_unc, [])
        # root offline -> không gọi exists() lên NAS cho 2001 record
        self.assertEqual([c for c in nas.exists_calls if c.startswith("\\\\")], [])


if __name__ == "__main__":
    unittest.main()
