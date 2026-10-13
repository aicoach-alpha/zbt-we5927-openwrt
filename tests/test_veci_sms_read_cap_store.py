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
    lib.veci_sms_store_arm_generated.argtypes = [
        ctypes.c_int, ptr, ctypes.c_uint, ctypes.c_uint64, ctypes.c_uint64,
        ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_int, ptr]
    lib.veci_sms_store_arm_generated.restype = ctypes.c_int
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


    def gen(self, **kw):
        out=(ctypes.c_ubyte*16)(*([0xEE]*16))
        rc=self.lib.veci_sms_store_arm_generated(
            kw.get("fd",self.fd),kw.get("session",A),
            kw.get("slot",4),kw.get("generation",39),
            kw.get("now",1000),kw.get("ttl",2000),
            kw.get("acl",1),kw.get("csrf",1),kw.get("consent",1),out)
        return rc,out

    def test_kernel_generated_nonce_roundtrip(self):
        rc,token=self.gen()
        self.assertEqual(rc,0)
        self.assertNotEqual(bytes(token),bytes(16))
        self.assertNotEqual(bytes(token),bytes([0xEE]*16))
        self.assertEqual(self.consume(nonce=token),0)
        self.assertEqual(self.consume(nonce=token),-errno.EACCES)

    def test_new_nonce_on_new_explicit_consent(self):
        rc,a=self.gen()
        self.assertEqual(rc,0)
        self.assertEqual(self.consume(nonce=a),0)
        rc,b=self.gen(now=2000)
        self.assertEqual(rc,0)
        self.assertNotEqual(bytes(a),bytes(b))
        self.assertEqual(self.consume(nonce=b,now=2001),0)

    def test_nonce_never_exported_if_acl_csrf_consent_invalid(self):
        for gate in ("acl","csrf","consent"):
            with self.subTest(gate=gate):
                rc,output=self.gen(**{gate:0})
                self.assertEqual(rc,-errno.EACCES)
                self.assertEqual(bytes(output),bytes(16))
                self.assertEqual(os.listdir(self.tmp.name),[])

    def test_busy_store_hides_new_random_candidate(self):
        rc,first=self.gen()
        self.assertEqual(rc,0)
        rc,blocked=self.gen(now=1001)
        self.assertEqual(rc,-errno.EBUSY)
        self.assertEqual(bytes(blocked),bytes(16))
        self.assertEqual(self.consume(nonce=first),0)

    def test_invalid_slot_does_not_return_nonce(self):
        rc,token=self.gen(slot=65536)
        self.assertEqual(rc,-errno.EACCES)
        self.assertEqual(bytes(token),bytes(16))
        self.assertEqual(os.listdir(self.tmp.name),[])

    def test_generated_nonce_mismatched_session_consumes(self):
        rc,token=self.gen()
        self.assertEqual(rc,0)
        self.assertEqual(self.consume(nonce=token,session=WRONG),-errno.EACCES)
        self.assertEqual(self.consume(nonce=token),-errno.EACCES)

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

    def test_expired_record_requires_new_explicit_consent(self):
        self.assertEqual(self.arm(ttl=10), 0)
        self.assertEqual(self.arm(now=1009, nonce=WRONG), -errno.EBUSY)
        self.assertEqual(self.arm(now=1010, nonce=WRONG, consent=0), -errno.EACCES)
        self.assertEqual(self.arm(now=1010, nonce=WRONG), 0)
        self.assertEqual(self.consume(), -errno.EACCES)
        self.assertEqual(self.consume(nonce=WRONG), -errno.EACCES)

    def test_corrupted_record_cannot_be_replaced_after_expiry(self):
        self.assertEqual(self.arm(ttl=10), 0)
        with open(Path(self.tmp.name) / "pending", "ab") as f:
            f.write(b"bad-data")
        self.assertEqual(self.arm(now=4000, nonce=WRONG), -errno.EBUSY)
        self.assertNotEqual(self.consume(), 0)
        self.assertEqual(self.arm(now=4000, nonce=WRONG), 0)
        self.assertEqual(self.consume(nonce=WRONG, now=4001), 0)

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
        self.assertTrue((Path(self.tmp.name) / "pending").is_symlink())  # Never follow/delete attacker link
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
