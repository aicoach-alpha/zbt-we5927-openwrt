"""HOST ONLY: real flock + PTY simulated modem SMS read/list smoke.

This test builds a compile-disabled-by-default *test harness* on Linux.
Never opens real /dev/ttyUSB, never accesses SIM or transmits real USSD.
"""
import ctypes
import errno
import fcntl
import os
from pathlib import Path
import pty
import select
import subprocess
import tempfile
import threading
import time
import tty
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "source/we5927-lte/src"


class Result(ctypes.Structure):
    _fields_ = [("records", ctypes.c_uint), ("status", ctypes.c_int)]


class PtySmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.so = str(Path(cls.tmp.name) / "libveci-serial-test.so")
        cmd = [
            "cc", "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
            "-DVECI_ENABLE_OFFLINE_PTY_HARNESS",
            "-fPIC", "-shared",
            str(SRC / "veci-serial-pty-smoke.c"),
            str(SRC / "veci-modem-session-lock.c"),
            str(SRC / "veci-modem-transaction.c"),
            str(SRC / "veci-at-framing.c"),
            str(SRC / "veci-modem-job-queue.c"),
            "-o", cls.so,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stderr)
        cls.lib = ctypes.CDLL(cls.so)
        cls.lib.veci_serial_sms_smoke_fd.argtypes = [
            ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
            ctypes.c_uint, ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(Result),
        ]
        cls.lib.veci_serial_sms_smoke_fd.restype = ctypes.c_int

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.tmp_local = tempfile.TemporaryDirectory()
        self.lock_path = str(Path(self.tmp_local.name) / "isolated-AT.lock").encode()
        self.master, self.slave = pty.openpty()
        tty.setraw(self.slave)
        self.threads = []

    def tearDown(self):
        for t in self.threads:
            t.join(timeout=1.0)
            self.assertFalse(t.is_alive(), "simulated modem thread leaked")
        os.close(self.master)
        os.close(self.slave)
        self.tmp_local.cleanup()

    def execute(self, kind=2, index=1, approved=1, timeout=1000):
        value = Result()
        rc = self.lib.veci_serial_sms_smoke_fd(
            self.slave, self.lock_path, kind, index, approved, timeout,
            ctypes.byref(value))
        self.assertEqual(rc, value.status)
        return rc, value.records

    def spawn(self, expected, reply_chunks, delay=0.0, after_read=None):
        expected = expected.encode()
        def worker():
            command = b""
            end = time.monotonic() + 2.0
            while not command.endswith(b"\r") and time.monotonic() < end:
                r, _, _ = select.select([self.master], [], [], 0.1)
                if r:
                    command += os.read(self.master, 128)
            self.assertEqual(command, expected)
            if after_read:
                after_read()
            if delay:
                time.sleep(delay)
            for part in reply_chunks:
                os.write(self.master, part.encode() if isinstance(part, str) else part)
                time.sleep(0.003)
        t = threading.Thread(target=worker, daemon=True)
        self.threads.append(t)
        t.start()

    def test_sms_read_record_offline(self):
        self.spawn("AT+CMGR=1\r", ['+CMGR: 0,,2\r\n', '000011\r\n', 'OK\r\n'])
        self.assertEqual(self.execute(), (0, 1))

    def test_sms_list_empty_inbox(self):
        self.spawn("AT+CMGL=4\r", ["OK\r\n"])
        self.assertEqual(self.execute(kind=1, index=0), (0, 0))

    def test_sms_list_with_two_records(self):
        self.spawn("AT+CMGL=4\r", [
            "+CMGL: 1,0,,2\r\n000011\r\n",
            "+CMGL: 2,0,,2\r\n000011\r\nOK\r\n",
        ])
        self.assertEqual(self.execute(kind=1, index=0), (0, 2))

    def test_fragmented_terminal_response(self):
        self.spawn("AT+CMGR=4\r", ["+CMGR: 0,,2\r", "\n000011\r", "\nO", "K\r", "\n"])
        self.assertEqual(self.execute(index=4), (0, 1))

    def test_unsolicited_cmti_does_not_count_as_record(self):
        self.spawn("AT+CMGR=7\r", [
            '+CMTI: "SM",9\r\n',
            "+CMGR: 0,,2\r\n000011\r\nOK\r\n",
        ])
        self.assertEqual(self.execute(index=7), (0, 1))

    def test_stale_cusd_poison_and_no_result(self):
        self.spawn("AT+CMGR=1\r", ['+CUSD: 0,"0041",72\r\n'])
        self.assertEqual(self.execute(), (-errno.EPROTO, 0))

    def test_malformed_pdu_cannot_succeed(self):
        self.spawn("AT+CMGR=1\r", ["+CMGR: 0,,2\r\n00NOPE\r\nOK\r\n"])
        self.assertEqual(self.execute(), (-errno.EPROTO, 0))

    def test_cms_error_not_reported_as_success(self):
        self.spawn("AT+CMGR=1\r", ["+CMS ERROR: 321\r\n"])
        self.assertEqual(self.execute(), (-errno.EPROTO, 0))

    def test_timeout_does_not_replay_at_command(self):
        self.spawn("AT+CMGR=1\r", [])
        self.assertEqual(self.execute(timeout=150), (-errno.ETIMEDOUT, 0))
        r, _, _ = select.select([self.master], [], [], 0.02)
        self.assertEqual(r, [])

    def test_reject_sending_sms_and_ussd(self):
        for kind in (3, 4, 999, 0):
            self.assertEqual(self.execute(kind=kind), (-errno.EINVAL, 0))

    def test_read_only_approved_exactly_once(self):
        for approval in (0, 2, -1):
            self.assertEqual(self.execute(approved=approval), (-errno.EACCES, 0))
        r, _, _ = select.select([self.master], [], [], 0.02)
        self.assertEqual(r, [])

    def test_read_index_allowlist(self):
        for index in (0, 256, 10000):
            self.assertEqual(self.execute(index=index), (-errno.EINVAL, 0))
        self.assertEqual(self.execute(kind=1, index=1), (-errno.EINVAL, 0))

    def test_lock_contention_prevents_command(self):
        lock = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(self.execute(), (-errno.EBUSY, 0))
            r, _, _ = select.select([self.master], [], [], 0.02)
            self.assertEqual(r, [])
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
            os.close(lock)

    def test_lock_held_from_send_through_final_terminal(self):
        received = threading.Event()
        unblock = threading.Event()
        output = []
        def worker():
            cmd = b""
            while not cmd.endswith(b"\r"):
                cmd += os.read(self.master, 64)
            self.assertEqual(cmd, b"AT+CMGR=1\r")
            received.set()
            self.assertTrue(unblock.wait(1.0))
            os.write(self.master, b"+CMGR: 0,,2\r\n000011\r\nOK\r\n")
        t = threading.Thread(target=worker, daemon=True)
        self.threads.append(t)
        t.start()
        def transaction():
            output.append(self.execute())
        t2 = threading.Thread(target=transaction, daemon=True)
        self.threads.append(t2)
        t2.start()
        self.assertTrue(received.wait(1.0))
        other = os.open(self.lock_path, os.O_RDWR)
        try:
            with self.assertRaises(BlockingIOError):
                fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(other)
            unblock.set()
        t2.join(timeout=2.0)
        self.assertEqual(output, [(0, 1)])

    def test_unlock_after_failure_allows_new_read(self):
        self.spawn("AT+CMGR=1\r", ["+CMS ERROR: 321\r\n"])
        self.assertEqual(self.execute(), (-errno.EPROTO, 0))
        self.spawn("AT+CMGR=2\r", ["+CMGR: 0,,2\r\n000011\r\nOK\r\n"])
        self.assertEqual(self.execute(index=2), (0, 1))

    def test_compile_gate_cannot_be_bypassed_silently(self):
        result = subprocess.run(
            ["cc", "-std=c99", "-fsyntax-only",
             str(SRC / "veci-serial-pty-smoke.c")],
            capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("offline PTY harness", result.stderr)

    def test_no_real_modem_path_or_usb_probe(self):
        source = (SRC / "veci-serial-pty-smoke.c").read_text()
        self.assertNotIn("/dev/ttyUSB", source)
        self.assertNotIn('AT+CUSD=1', source)
        self.assertNotIn("AT+CMGS=", source)
        self.assertNotIn("AT+CMGD=", source)
        self.assertNotIn("syslog(", source)
        self.assertNotIn("fwrite(", source)


if __name__ == "__main__":
    unittest.main()
