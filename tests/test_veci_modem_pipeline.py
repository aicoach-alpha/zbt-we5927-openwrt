"""Native-C offline integration: AT byte stream -> framing -> FIFO session.

No real modem, no AT command send, no network or local device access.
"""
import ctypes
import errno
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_veci_at_framing import Frame, CALLBACK
from test_veci_modem_job_queue import Queue

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "source/we5927-lte/src"
LIST, READ, USSD = 1, 2, 3
WAITING, COMPLETE, INPUT_REQUIRED = 0, 1, 2


class IntegratedPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        cls.so = str(Path(cls.build.name) / "libveci-pipeline.so")
        p = subprocess.run([
            "cc", "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
            "-fPIC", "-shared", str(CODE / "veci-at-framing.c"),
            str(CODE / "veci-modem-job-queue.c"), "-o", cls.so
        ], capture_output=True, text=True)
        if p.returncode:
            raise AssertionError(p.stderr)
        cls.lib = ctypes.CDLL(cls.so)
        cls.lib.veci_frame_init.argtypes = [ctypes.POINTER(Frame)]
        cls.lib.veci_frame_feed.argtypes = [
            ctypes.POINTER(Frame), ctypes.c_char_p, ctypes.c_size_t,
            CALLBACK, ctypes.c_void_p]
        cls.lib.veci_frame_feed.restype = ctypes.c_int
        cls.lib.veci_frame_finish.argtypes = [
            ctypes.POINTER(Frame), CALLBACK, ctypes.c_void_p]
        cls.lib.veci_frame_finish.restype = ctypes.c_int
        cls.lib.veci_jobs_init.argtypes = [ctypes.POINTER(Queue)]
        cls.lib.veci_jobs_submit.argtypes = [
            ctypes.POINTER(Queue), ctypes.c_uint32, ctypes.c_int, ctypes.c_int]
        cls.lib.veci_jobs_submit.restype = ctypes.c_int
        cls.lib.veci_jobs_begin.argtypes = [
            ctypes.POINTER(Queue), ctypes.c_int64, ctypes.c_int,
            ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_int)]
        cls.lib.veci_jobs_begin.restype = ctypes.c_int
        cls.lib.veci_jobs_consume.argtypes = [
            ctypes.POINTER(Queue), ctypes.c_uint32, ctypes.c_int,
            ctypes.c_char_p, ctypes.c_int, ctypes.c_int64]
        cls.lib.veci_jobs_consume.restype = ctypes.c_int
        cls.lib.veci_jobs_expire.argtypes = [
            ctypes.POINTER(Queue), ctypes.c_int64]
        cls.lib.veci_jobs_expire.restype = ctypes.c_int
        cls.lib.veci_jobs_finish.argtypes = [
            ctypes.POINTER(Queue), ctypes.c_uint32]
        cls.lib.veci_jobs_finish.restype = ctypes.c_int

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.q = Queue()
        self.f = Frame()
        self.lib.veci_jobs_init(ctypes.byref(self.q))
        self.lib.veci_frame_init(ctypes.byref(self.f))
        self.results = []
        self.mode = None

        def handler(event, raw, metadata, _context):
            # Only output status/metadata here. Never persist raw SMS/USSD.
            result = self.lib.veci_jobs_consume(
                ctypes.byref(self.q), 123, event, raw, metadata, 1000)
            self.results.append(result)

        self.cb = CALLBACK(handler)

    def begin(self, kind):
        self.assertEqual(self.lib.veci_jobs_submit(
            ctypes.byref(self.q), 123, kind, 1), 0)
        identifier, selected = ctypes.c_uint32(), ctypes.c_int()
        self.assertEqual(self.lib.veci_jobs_begin(
            ctypes.byref(self.q), 1000, 5000,
            ctypes.byref(identifier), ctypes.byref(selected)), 0)
        self.assertEqual((identifier.value, selected.value), (123, kind))

    def push(self, *pieces):
        for data in pieces:
            if isinstance(data, str):
                data = data.encode("ascii")
            ret = self.lib.veci_frame_feed(
                ctypes.byref(self.f), data, len(data), self.cb, None)
            if ret < 0:
                return ret
        return 0

    def test_fragmented_sms_list_requires_header_body_and_terminal(self):
        self.begin(LIST)
        self.assertEqual(self.push("+CMGL:", " 1,0,,2\r", "\n00", "0011\r\n", "OK\r\n"), 0)
        self.assertEqual(self.results[-1], COMPLETE)
        self.assertEqual(self.q.pdu_count, 1)
        self.assertEqual(self.lib.veci_jobs_finish(ctypes.byref(self.q), 123), 0)

    def test_urc_sms_pdu_cannot_be_counted_as_inbox(self):
        self.begin(LIST)
        self.assertEqual(self.push(
            "+CMT: ,2\r\n000011\r\n",
            "+CMGL: 2,0,,2\r\n000011\r\nOK\r\n"), 0)
        self.assertEqual(self.q.pdu_count, 1)
        self.assertEqual(self.results[-1], COMPLETE)

    def test_incoming_urc_sms_cannot_forge_read_result(self):
        self.begin(READ)
        self.assertEqual(self.push("+CMT: ,2\r\n000011\r\nOK\r\n"), 0)
        self.assertEqual(self.results[-1], -errno.EPROTO)
        self.assertTrue(self.q.poisoned)

    def test_async_ussd_urc_arrives_after_command_ack(self):
        self.begin(USSD)
        self.assertEqual(self.push("OK\r\n"), 0)
        self.assertEqual(self.results[-1], WAITING)
        self.assertEqual(self.push('+CUSD: 0,"0053006900730061",72\r\n'), 0)
        self.assertEqual(self.results[-1], COMPLETE)

    def test_async_ussd_urc_arrives_before_command_ack(self):
        self.begin(USSD)
        self.assertEqual(self.push('+CUSD: 0,"00530069",72\r\nOK\r\n'), 0)
        self.assertEqual(self.results[-1], COMPLETE)

    def test_interactive_ussd_requires_explicit_user_continuation(self):
        self.begin(USSD)
        self.assertEqual(self.push('OK\r\n+CUSD: 1,"004F004B",72\r\n'), 0)
        self.assertEqual(self.results[-1], INPUT_REQUIRED)
        self.assertEqual(self.lib.veci_jobs_finish(ctypes.byref(self.q), 123), -errno.EBUSY)

    def test_ussd_ack_without_urc_expires_without_retry(self):
        self.begin(USSD)
        self.assertEqual(self.push("OK\r\n"), 0)
        self.assertEqual(self.lib.veci_jobs_expire(ctypes.byref(self.q), 6001),
                         -errno.ETIMEDOUT)
        self.assertTrue(self.q.poisoned)

    def test_bogus_pdu_ok_text_does_not_end_transaction(self):
        self.begin(READ)
        self.assertEqual(self.push("+CMGR: 0,,2\r\nOK\r\n"), -1)
        self.assertEqual(self.results[-1], -errno.EPROTO)
        self.assertEqual(self.q.pdu_count, 0)

    def test_incomplete_pdu_header_is_detected_at_eof(self):
        self.begin(READ)
        self.assertEqual(self.push("+CMGR: 0,,2\r\n"), 0)
        self.assertEqual(self.lib.veci_frame_finish(
            ctypes.byref(self.f), self.cb, None), -1)
        self.assertEqual(self.results[-1], -errno.EPROTO)

    def test_sms_text_mode_record_fails_closed(self):
        self.begin(LIST)
        self.assertEqual(self.push(
            '+CMGL: 1,"REC READ","+62812","","26/10/12"\r\n'), -1)
        self.assertEqual(self.results[-1], -errno.EPROTO)

    def test_unsolicited_cusd_during_sms_list_does_not_finish_job(self):
        self.begin(LIST)
        self.assertEqual(self.push('+CUSD: 0,"0031",72\r\n'), 0)
        self.assertEqual(self.results[-1], WAITING)
        self.assertEqual(self.push("OK\r\n"), 0)
        self.assertEqual(self.results[-1], COMPLETE)


if __name__ == "__main__":
    unittest.main()
