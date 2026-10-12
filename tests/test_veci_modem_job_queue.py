"""Offline native-C FIFO/state tests. Never opens /dev, sends AT or reads SMS."""
import ctypes
import errno
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source/we5927-lte/src/veci-modem-job-queue.c"
LIST, READ, USSD = 1, 2, 3
OTHER, OK, ERROR, SMS_PDU, SMS_NOTICE, USSD_EVENT, PROTOCOL_ERROR = range(7)
WAITING, COMPLETE, INPUT_REQUIRED = range(3)


class Job(ctypes.Structure):
    _fields_ = [("id", ctypes.c_uint32), ("kind", ctypes.c_int)]


class Queue(ctypes.Structure):
    _fields_ = [
        ("pending", Job * 4),
        ("active", Job),
        ("head", ctypes.c_uint),
        ("count", ctypes.c_uint),
        ("active_valid", ctypes.c_int),
        ("poisoned", ctypes.c_int),
        ("deadline_ms", ctypes.c_int64),
        ("started_ms", ctypes.c_int64),
        ("acked", ctypes.c_int),
        ("ussd_received", ctypes.c_int),
        ("ussd_mode", ctypes.c_int),
        ("expected_pdu", ctypes.c_int),
        ("pdu_count", ctypes.c_uint),
        ("result", ctypes.c_int),
    ]


class QueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.libfile = str(Path(cls.tmp.name) / "libveci-queue.so")
        p = subprocess.run(
            ["cc", "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
             "-fPIC", "-shared", str(SOURCE), "-o", cls.libfile],
            capture_output=True, text=True)
        if p.returncode:
            raise AssertionError(p.stderr)
        cls.lib = ctypes.CDLL(cls.libfile)
        cls.lib.veci_jobs_init.argtypes = [ctypes.POINTER(Queue)]
        cls.lib.veci_jobs_reset.argtypes = [ctypes.POINTER(Queue)]
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
        cls.lib.veci_jobs_finish.argtypes = [ctypes.POINTER(Queue), ctypes.c_uint32]
        cls.lib.veci_jobs_finish.restype = ctypes.c_int
        cls.lib.veci_jobs_abort.argtypes = [ctypes.POINTER(Queue), ctypes.c_uint32]
        cls.lib.veci_jobs_abort.restype = ctypes.c_int

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.q = Queue()
        self.lib.veci_jobs_init(ctypes.byref(self.q))
        self.now = 1000

    def submit(self, identifier=1, kind=USSD, consent=1):
        return self.lib.veci_jobs_submit(ctypes.byref(self.q), identifier, kind, consent)

    def begin(self, timeout=2000, when=1000):
        identifier = ctypes.c_uint32(0)
        kind = ctypes.c_int(0)
        result = self.lib.veci_jobs_begin(
            ctypes.byref(self.q), when, timeout,
            ctypes.byref(identifier), ctypes.byref(kind))
        return result, identifier.value, kind.value

    def feed(self, event, line=b"", meta=0, identifier=1, when=1000):
        return self.lib.veci_jobs_consume(
            ctypes.byref(self.q), identifier, event, line, meta, when)

    def finish(self, identifier=1):
        return self.lib.veci_jobs_finish(ctypes.byref(self.q), identifier)

    def test_explicit_approval_required_even_for_read(self):
        for kind in (LIST, READ, USSD):
            self.assertEqual(self.submit(1, kind, 0), -errno.EACCES)
        self.assertEqual(self.q.count, 0)

    def test_invalid_id_kind_and_duplicates_rejected(self):
        self.assertEqual(self.submit(0), -errno.EINVAL)
        self.assertEqual(self.submit(1, 55), -errno.EINVAL)
        self.assertEqual(self.submit(1), 0)
        self.assertEqual(self.submit(1), -errno.EEXIST)

    def test_capacity_fixed_to_four_no_payload_storage(self):
        for i in range(1, 5):
            self.assertEqual(self.submit(i), 0)
        self.assertEqual(self.submit(5), -errno.ENOSPC)
        self.assertEqual(self.q.count, 4)
        self.assertFalse(hasattr(self.q, "sms_body"))
        self.assertFalse(hasattr(self.q, "phone_number"))

    def test_fifo_order_and_explicit_finish(self):
        for i in (12, 13, 14):
            self.assertEqual(self.submit(i, LIST), 0)
        for i in (12, 13, 14):
            self.assertEqual(self.begin(), (0, i, LIST))
            self.assertEqual(self.begin()[0], -errno.EBUSY)
            self.assertEqual(self.feed(OK, identifier=i), COMPLETE)
            self.assertEqual(self.finish(i), 0)
        self.assertEqual(self.begin()[0], -errno.ENOENT)

    def test_usss_ack_not_interpreted_as_final_response(self):
        self.assertEqual(self.submit(), 0)
        self.assertEqual(self.begin(), (0, 1, USSD))
        self.assertEqual(self.feed(OK), WAITING)
        self.assertEqual(self.finish(), -errno.EBUSY)
        self.assertEqual(self.feed(USSD_EVENT, b'+CUSD: 0,"0041",72', 0), COMPLETE)
        self.assertEqual(self.finish(), 0)

    def test_ussd_urc_before_ack_is_valid(self):
        self.submit()
        self.begin()
        self.assertEqual(self.feed(USSD_EVENT, b"+CUSD: 0", 0), WAITING)
        self.assertEqual(self.feed(OK), COMPLETE)

    def test_ussd_interactive_never_autocompletes(self):
        self.submit()
        self.begin()
        self.assertEqual(self.feed(OK), WAITING)
        self.assertEqual(self.feed(USSD_EVENT, b"+CUSD: 1", 1), INPUT_REQUIRED)
        self.assertEqual(self.finish(), -errno.EBUSY)
        self.assertEqual(self.q.active_valid, 1)

    def test_ussd_repeated_or_invalid_urc_poisons(self):
        self.submit()
        self.begin()
        self.feed(USSD_EVENT, b"+CUSD: 0", 0)
        self.assertEqual(self.feed(USSD_EVENT, b"+CUSD: 0", 0), -errno.EPROTO)
        self.assertEqual(self.q.poisoned, 1)

    def test_sms_list_allows_empty_inbox(self):
        self.submit(kind=LIST)
        self.begin()
        self.assertEqual(self.feed(OK), COMPLETE)
        self.assertEqual(self.q.pdu_count, 0)

    def test_sms_list_counts_only_expected_pdu(self):
        self.submit(kind=LIST)
        self.begin()
        self.assertEqual(self.feed(OTHER, b"+CMGL: 1,0,,2"), WAITING)
        self.assertEqual(self.feed(SMS_PDU, b"000011"), WAITING)
        self.assertEqual(self.feed(OK), COMPLETE)
        self.assertEqual(self.q.pdu_count, 1)

    def test_unsolicited_sms_never_counts_as_inbox(self):
        self.submit(kind=READ)
        self.begin()
        self.assertEqual(self.feed(OTHER, b"+CMT: ,2"), WAITING)
        self.assertEqual(self.feed(SMS_PDU, b"000011"), WAITING)
        self.assertEqual(self.feed(OK), -errno.EPROTO)
        self.assertEqual(self.q.pdu_count, 0)

    def test_sms_read_requires_exactly_one_record(self):
        self.submit(kind=READ)
        self.begin()
        self.assertEqual(self.feed(OTHER, b"+CMGR: 0,,2"), WAITING)
        self.assertEqual(self.feed(SMS_PDU, b"000011"), WAITING)
        self.assertEqual(self.feed(OK), COMPLETE)

    def test_sms_read_missing_record_fails_closed(self):
        self.submit(kind=READ)
        self.begin()
        self.assertEqual(self.feed(OK), -errno.EPROTO)

    def test_sms_header_without_pdu_fails_closed(self):
        self.submit(kind=LIST)
        self.begin()
        self.feed(OTHER, b"+CMGL: 1,0,,2")
        self.assertEqual(self.feed(OK), -errno.EPROTO)

    def test_error_and_protocol_error_poison_pending_jobs(self):
        for event in (ERROR, PROTOCOL_ERROR):
            self.lib.veci_jobs_reset(ctypes.byref(self.q))
            self.submit(1)
            self.submit(2)
            self.begin()
            self.assertEqual(self.feed(event), -errno.EPROTO)
            self.assertEqual(self.q.count, 0)
            self.assertEqual(self.submit(3), -errno.EIO)

    def test_expired_job_discards_queue_with_no_auto_retry(self):
        self.submit(1)
        self.submit(2)
        self.begin(250)
        self.assertEqual(self.lib.veci_jobs_expire(ctypes.byref(self.q), 1249), WAITING)
        self.assertEqual(self.lib.veci_jobs_expire(ctypes.byref(self.q), 1250), -errno.ETIMEDOUT)
        self.assertEqual(self.q.count, 0)
        self.assertEqual(self.begin()[0], -errno.EIO)
        self.lib.veci_jobs_reset(ctypes.byref(self.q))
        self.assertEqual(self.begin()[0], -errno.ENOENT)

    def test_events_past_deadline_rejected(self):
        self.submit()
        self.begin(timeout=100)
        self.assertEqual(self.feed(OK, when=1100), -errno.ETIMEDOUT)

    def test_wrong_id_never_advances_other_transaction(self):
        self.submit(1)
        self.begin()
        self.assertEqual(self.feed(OK, identifier=9), -errno.ENOENT)
        self.assertFalse(self.q.acked)

    def test_abort_keeps_queue_poisoned_until_explicit_reset(self):
        self.submit(1)
        self.submit(2)
        self.begin()
        self.assertEqual(self.lib.veci_jobs_abort(ctypes.byref(self.q), 1), -errno.ECANCELED)
        self.assertEqual(self.q.count, 0)
        self.assertEqual(self.submit(3), -errno.EIO)

    def test_timeout_limits_and_64bit_clock_overflow(self):
        self.submit()
        self.assertEqual(self.begin(timeout=99)[0], -errno.EINVAL)
        self.assertEqual(self.begin(timeout=30001)[0], -errno.EINVAL)
        self.assertEqual(self.begin(2000, 2**63 - 100)[0], -errno.EINVAL)
        self.assertEqual(self.begin(2000, -1)[0], -errno.EINVAL)
        self.assertEqual(self.begin(), (0, 1, USSD))

    def test_duplicate_active_id_rejected(self):
        self.submit(1)
        self.begin()
        self.assertEqual(self.submit(1), -errno.EEXIST)

    def test_clock_regression_poisons_no_replay(self):
        self.submit(1)
        self.submit(2)
        self.begin()
        self.assertEqual(self.feed(OK, when=999), -errno.EPROTO)
        self.assertEqual(self.q.count, 0)
        self.assertEqual(self.begin()[0], -errno.EIO)

    def test_bad_event_code_is_not_ignored(self):
        self.submit()
        self.begin()
        self.assertEqual(self.feed(77), -errno.EPROTO)
        self.assertTrue(self.q.poisoned)

    def test_only_exact_approval_value_allowed(self):
        self.assertEqual(self.submit(consent=2), -errno.EACCES)
        self.assertEqual(self.submit(consent=-1), -errno.EACCES)
        self.assertEqual(self.submit(consent=1), 0)

    def test_no_modem_io_no_network_or_logging(self):
        src = SOURCE.read_text()
        self.assertIn("VECI_JOBS_MAX 4", src)
        self.assertNotIn("/dev/ttyUSB", src)
        self.assertNotIn("AT+CMGS=", src)
        self.assertNotIn("AT+CUSD=1", src)
        for text in ("printf(", "system(", "syslog(", "socket(", "open("):
            self.assertNotIn(text, src)


if __name__ == "__main__":
    unittest.main()
