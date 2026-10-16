"""Offline tests for full-session modem lock admission; no hardware access."""
import ctypes
import errno
import fcntl
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source/we5927-lte/src/veci-modem-session-lock.c"


class SessionLockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        cls.so = str(Path(cls.build.name) / "libveci-modem-lock.so")
        compile_result = subprocess.run(
            ["cc", "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
             "-fPIC", "-shared", str(SOURCE), "-o", cls.so],
            capture_output=True, text=True,
        )
        if compile_result.returncode:
            raise AssertionError(compile_result.stderr)
        cls.lib = ctypes.CDLL(cls.so)
        cls.lib.veci_at_session_lock_path.argtypes = [ctypes.c_char_p, ctypes.c_int]
        cls.lib.veci_at_session_lock_path.restype = ctypes.c_int
        cls.lib.veci_at_session_unlock.argtypes = [ctypes.c_int]

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.lock = (Path(self.temp.name) / "we5927-at.lock")
        self.filename = os.fsencode(str(self.lock))

    def acquire(self, timeout=0, name=None):
        return self.lib.veci_at_session_lock_path(name or self.filename, timeout)

    def release(self, fd):
        self.lib.veci_at_session_unlock(fd)

    def test_uncontended_lock_owned_until_release(self):
        fd = self.acquire()
        self.assertGreaterEqual(fd, 0)
        self.assertEqual(self.lock.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.acquire(), -errno.EBUSY)
        self.release(fd)
        new_fd = self.acquire()
        self.assertGreaterEqual(new_fd, 0)
        self.release(new_fd)

    def test_native_lock_interoperates_with_existing_shell_flock(self):
        fd = os.open(self.lock, os.O_CREAT | os.O_RDWR, 0o600)
        self.addCleanup(os.close, fd)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.assertEqual(self.acquire(), -errno.EBUSY)
        fcntl.flock(fd, fcntl.LOCK_UN)
        acquired = self.acquire()
        self.assertGreaterEqual(acquired, 0)
        self.release(acquired)

    def test_bounded_wait_can_acquire_after_release(self):
        fd = self.acquire()
        self.assertGreaterEqual(fd, 0)
        def release_soon():
            time.sleep(0.12)
            self.release(fd)
        t = threading.Thread(target=release_soon)
        t.start()
        try:
            acquired = self.acquire(900)
            self.assertGreaterEqual(acquired, 0)
            self.release(acquired)
        finally:
            t.join(timeout=2)

    def test_bounded_wait_expires_never_blocks_forever(self):
        fd = self.acquire()
        self.assertGreaterEqual(fd, 0)
        try:
            start = time.monotonic()
            self.assertEqual(self.acquire(150), -errno.ETIMEDOUT)
            elapsed = time.monotonic() - start
            self.assertLess(elapsed, 1)
        finally:
            self.release(fd)

    def test_reject_excessive_wait_and_invalid_path(self):
        self.assertEqual(self.acquire(-1), -errno.EINVAL)
        self.assertEqual(self.acquire(2001), -errno.EINVAL)
        self.assertEqual(self.lib.veci_at_session_lock_path(b"", 0), -errno.EINVAL)

    def test_symlink_attack_is_rejected(self):
        victim = Path(self.temp.name) / "victim"
        victim.write_text("unchanged")
        self.lock.symlink_to(victim)
        fd = self.acquire()
        self.assertLess(fd, 0)
        self.assertEqual(victim.read_text(), "unchanged")

    def test_hardlinked_lock_is_rejected(self):
        self.lock.touch(mode=0o600)
        other = Path(self.temp.name) / "other-link"
        os.link(self.lock, other)
        self.assertEqual(self.acquire(), -errno.EPERM)

    def test_no_modem_or_user_data_io(self):
        source = SOURCE.read_text()
        self.assertIn('"/var/lock/we5927-at.lock"', source)
        self.assertIn("O_NOFOLLOW", source)
        self.assertIn("O_CLOEXEC", source)
        self.assertIn("LOCK_EX | LOCK_NB", source)
        self.assertNotIn("AT+CMGS", source)
        self.assertNotIn("AT+CUSD=", source)
        for forbidden in ("ttyUSB", "printf(", "system(", "exec(", "curl ", "wget "):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
