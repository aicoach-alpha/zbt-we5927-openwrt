"""Cross-process VeCI private capability store, entirely host/offline."""
import ctypes
import errno
import multiprocessing as mp
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "source/we5927-lte/src"
A = (ctypes.c_ubyte * 16)(*range(1, 17))
B = (ctypes.c_ubyte * 16)(*range(51, 67))
WRONG = (ctypes.c_ubyte * 16)(*range(101, 117))

def load_library(path):
    lib = ctypes.CDLL(str(path))
    ptr = ctypes.POINTER(ctypes.c_ubyte)
    lib.veci_sms_store_arm.argtypes = [
        ctypes.c_int, ptr, ptr, ctypes.c_uint, ctypes.c_uint64,
        ctypes.c_uint64, ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    lib.veci_sms_store_arm.restype = ctypes.c_int
    lib.veci_sms_store_consume.argtypes = [
        ctypes.c_int, ptr, ptr, ctypes.c_uint, ctypes.c_uint64, ctypes.c_uint64]
    lib.veci_sms_store_consume.restype = ctypes.c_int
    return lib

def concurrent_consume(path, library, start, out):
    lib = load_library(library)
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)  # own open file description
    try:
        start.wait(5)
        out.put(lib.veci_sms_store_consume(fd, A, B, 4, 39, 1001))
    finally:
        os.close(fd)

class StoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("/dev/shm").is_dir():
            raise unittest.SkipTest("No tmpfs /dev/shm on this CI runner")
        cls.build = tempfile.TemporaryDirectory()
        cls.so = str(Path(cls.build.name) / "libstore.so")
        result = subprocess.run([
            "cc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-O2",
            "-fPIC", "-shared", "-I", str(BASE),
            str(BASE / "veci-sms-read-capability.c"),
            str(BASE / "veci-sms-read-cap-store.c"), "-o", cls.so],
            capture_output=True, text=True, timeout=20)
        if result.returncode:
            raise AssertionError(result.stderr)
        cls.lib = load_library(cls.so)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir="/dev/shm")
        self.addCleanup(self.tmp.cleanup)
        self.fd = os.open(self.tmp.name, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, self.fd)

    def arm(self, **kw):
        return self.lib.veci_sms_store_arm(
            kw.get("fd", self.fd), kw.get("session", A), kw.get("nonce", B),
            kw.get("slot", 4), kw.get("generation", 39),
            kw.get("now", 1000), kw.get("ttl", 2000),
            kw.get("acl", 1), kw.get("csrf", 1), kw.get("consent", 1))

    def consume(self, **kw):
        return self.lib.veci_sms_store_consume(
            kw.get("fd", self.fd), kw.get("session", A), kw.get("nonce", B),
            kw.get("slot", 4), kw.get("generation", 39),
            kw.get("now", 1001))

    def test_happy_path_distinct_open_descriptors_and_replay(self):
        self.assertEqual(self.arm(), 0)
        second = os.open(self.tmp.name, os.O_RDONLY | os.O_DIRECTORY)
        try:
            self.assertEqual(self.consume(fd=second), 0)
            self.assertEqual(self.consume(), -errno.EACCES)
            self.assertEqual(os.listdir(self.tmp.name), [])
        finally:
            os.close(second)

    def test_wrong_nonce_or_session_slot_generation_burns_token(self):
        for wrong in ({"nonce": WRONG}, {"session": WRONG},
                      {"slot": 5}, {"generation": 40}):
            with self.subTest(wrong=wrong):
                self.assertEqual(self.arm(), 0)
                self.assertEqual(self.consume(**wrong), -errno.EACCES)
                self.assertEqual(self.consume(), -errno.EACCES)

    def test_expiry_and_clock_rollback_burn(self):
        for moment in (999, 3000):
            with self.subTest(moment=moment):
                self.assertEqual(self.arm(), 0)
                self.assertEqual(self.consume(now=moment), -errno.EACCES)
                self.assertEqual(self.consume(), -errno.EACCES)

    def test_no_overwrite_or_unapproved_arm(self):
        self.assertEqual(self.arm(), 0)
        self.assertEqual(self.arm(), -errno.EBUSY)
        self.assertEqual(self.consume(), 0)
        for flag in ("acl", "csrf", "consent"):
            self.assertEqual(self.arm(**{flag: 0}), -errno.EACCES)
            self.assertEqual(os.listdir(self.tmp.name), [])

    def test_tmpfs_directory_permissions(self):
        self.assertEqual(self.arm(), 0)
        self.assertEqual(self.consume(), 0)
        os.chmod(self.tmp.name, 0o755)
        self.assertEqual(self.arm(), -errno.EPERM)
        self.assertEqual(self.consume(), -errno.EPERM)
        os.chmod(self.tmp.name, 0o700)
        self.assertEqual(self.arm(), 0)
        self.assertEqual(self.consume(), 0)

    def test_reject_disk_based_private_directory(self):
        with tempfile.TemporaryDirectory() as path:
            fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
            try:
                self.assertEqual(self.arm(fd=fd), -errno.EPERM)
            finally:
                os.close(fd)

    def test_corruption_is_burned_without_leaking(self):
        self.assertEqual(self.arm(), 0)
        with open(Path(self.tmp.name) / "pending", "ab") as f:
            f.write(b"garbage")
        self.assertNotEqual(self.consume(), 0)
        self.assertEqual(os.listdir(self.tmp.name), [])

    def test_malicious_symlink_does_not_get_followed(self):
        os.symlink("/etc/passwd", Path(self.tmp.name) / "pending")
        self.assertEqual(self.arm(), -errno.EBUSY)
        self.assertEqual(self.consume(), -errno.EACCES)
        self.assertFalse((Path(self.tmp.name) / "pending").exists())
        self.assertTrue(Path("/etc/passwd").exists())

    def test_parallel_consumers_only_one_success(self):
        self.assertEqual(self.arm(), 0)
        start = mp.Event()
        result = mp.Queue()
        workers = [mp.Process(target=concurrent_consume,
                  args=(self.tmp.name, self.so, start, result)) for _ in range(2)]
        for worker in workers:
            worker.start()
        start.set()
        outcomes = [result.get(timeout=5) for _ in workers]
        for worker in workers:
            worker.join(5)
            self.assertEqual(worker.exitcode, 0)
        self.assertEqual(outcomes.count(0), 1)
        self.assertEqual(len(outcomes), 2)

    def test_source_only_boundary(self):
        code = (BASE / "veci-sms-read-cap-store.c").read_text()
        self.assertNotIn("AT+CMGR", code)
        self.assertNotIn("/dev/ttyUSB", code)
        self.assertNotIn("ubus_rpc_session", code)
        self.assertNotIn("system(", code)
        self.assertNotIn("popen(", code)
        self.assertNotIn("syslog(", code)
        self.assertNotIn("logger(", code)
        firmware = (ROOT / "source/we5927-lte/Makefile").read_text()
        self.assertNotIn("veci-sms-read-cap-store", firmware)

if __name__ == "__main__":
    unittest.main()
