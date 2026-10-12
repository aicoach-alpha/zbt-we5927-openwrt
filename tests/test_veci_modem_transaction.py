"""Offline native coordinator + real parser + queue; NO modem or AT TX.

The fake lock descriptor is a temporary, local file. This validates state
transitions, not physical flock ownership or W907 URC attribution.
"""
import ctypes
import errno
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_veci_at_framing import Frame
from test_veci_modem_job_queue import Queue

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "source/we5927-lte/src"
LIST, READ, USSD = 1, 2, 3
IDLE, ARMED, INFLIGHT, COMPLETE, INTERACTIVE, QUARANTINED = range(6)


class Transaction(ctypes.Structure):
    _fields_ = [
        ("frame", Frame),
        ("queue", Queue),
        ("epoch", ctypes.c_uint64),
        ("lock_fd", ctypes.c_int),
        ("job_id", ctypes.c_uint32),
        ("kind", ctypes.c_int),
        ("state", ctypes.c_int),
        ("first_error", ctypes.c_int),
    ]


class SessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.library_path = str(Path(cls.tempdir.name) / "libveci-txn.so")
        comp = subprocess.run(
            ["cc", "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
             "-fPIC", "-shared",
             str(SRC / "veci-at-framing.c"),
             str(SRC / "veci-modem-job-queue.c"),
             str(SRC / "veci-modem-transaction.c"),
             "-o", cls.library_path],
            capture_output=True, text=True)
        if comp.returncode:
            raise AssertionError(comp.stderr)
        cls.lib = ctypes.CDLL(cls.library_path)
        cls.lib.veci_txn_init.argtypes = [ctypes.POINTER(Transaction)]
        cls.lib.veci_txn_submit.argtypes = [
            ctypes.POINTER(Transaction), ctypes.c_uint32,
            ctypes.c_int, ctypes.c_int]
        cls.lib.veci_txn_submit.restype = ctypes.c_int
        cls.lib.veci_txn_arm.argtypes = [
            ctypes.POINTER(Transaction), ctypes.c_uint64,
            ctypes.c_int, ctypes.c_int64, ctypes.c_int,
            ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_int)]
        cls.lib.veci_txn_arm.restype = ctypes.c_int
        cls.lib.veci_txn_issued.argtypes = [
            ctypes.POINTER(Transaction), ctypes.c_uint64, ctypes.c_uint32]
        cls.lib.veci_txn_issued.restype = ctypes.c_int
        cls.lib.veci_txn_feed.argtypes = [
            ctypes.POINTER(Transaction), ctypes.c_uint64,
            ctypes.c_uint32, ctypes.c_char_p, ctypes.c_size_t,
            ctypes.c_int64]
        cls.lib.veci_txn_feed.restype = ctypes.c_int
        cls.lib.veci_txn_tick.argtypes = [
            ctypes.POINTER(Transaction), ctypes.c_int64]
        cls.lib.veci_txn_tick.restype = ctypes.c_int
        cls.lib.veci_txn_finish.argtypes = [
            ctypes.POINTER(Transaction), ctypes.c_uint64, ctypes.c_uint32]
        cls.lib.veci_txn_finish.restype = ctypes.c_int
        cls.lib.veci_txn_abort.argtypes = [
            ctypes.POINTER(Transaction), ctypes.c_uint64, ctypes.c_uint32]
        cls.lib.veci_txn_abort.restype = ctypes.c_int
        cls.lib.veci_txn_resync.argtypes = [
            ctypes.POINTER(Transaction), ctypes.c_uint64, ctypes.c_int]
        cls.lib.veci_txn_resync.restype = ctypes.c_int

    @classmethod
    def tearDownClass(cls):
        cls.tempdir.cleanup()

    def setUp(self):
        self.tx = Transaction()
        self.lib.veci_txn_init(ctypes.byref(self.tx))
        self.fake_fd = tempfile.TemporaryFile()
        self.epoch = 1
        self.id = 123
        self.now = 1000

    def tearDown(self):
        self.fake_fd.close()

    def submit(self, kind=USSD, ident=None, approval=1):
        if ident is None:
            ident = self.id
        return self.lib.veci_txn_submit(
            ctypes.byref(self.tx), ident, kind, approval)

    def arm(self, epoch=None, fd=None, now=None, timeout=2000):
        ident = ctypes.c_uint32()
        kind = ctypes.c_int()
        rc = self.lib.veci_txn_arm(
            ctypes.byref(self.tx),
            self.epoch if epoch is None else epoch,
            self.fake_fd.fileno() if fd is None else fd,
            self.now if now is None else now, timeout,
            ctypes.byref(ident), ctypes.byref(kind))
        return rc, ident.value, kind.value

    def issued(self, epoch=None, ident=None):
        return self.lib.veci_txn_issued(
            ctypes.byref(self.tx),
            self.epoch if epoch is None else epoch,
            self.id if ident is None else ident)

    def feed(self, data, epoch=None, ident=None, now=None):
        data = data.encode("ascii") if isinstance(data, str) else data
        return self.lib.veci_txn_feed(
            ctypes.byref(self.tx),
            self.epoch if epoch is None else epoch,
            self.id if ident is None else ident,
            data, len(data),
            self.now if now is None else now)

    def finish(self, epoch=None, ident=None):
        return self.lib.veci_txn_finish(
            ctypes.byref(self.tx),
            self.epoch if epoch is None else epoch,
            self.id if ident is None else ident)

    def resync(self, new_epoch=2, confirmed=1):
        return self.lib.veci_txn_resync(
            ctypes.byref(self.tx), new_epoch, confirmed)

    def begin(self, kind=USSD):
        self.assertEqual(self.submit(kind), 0)
        self.assertEqual(self.arm(), (0, self.id, kind))
        self.assertEqual(self.issued(), 0)

    def test_initial_state_no_secret_data(self):
        self.assertEqual(self.tx.state, IDLE)
        self.assertEqual(self.tx.lock_fd, -1)
        self.assertEqual(self.tx.epoch, 0)

    def test_no_approval_no_queue(self):
        self.assertEqual(self.submit(READ, approval=0), -errno.EACCES)
        self.assertEqual(self.arm()[0], -errno.ENOENT)

    def test_fake_fd_rejected_before_consume_if_invalid(self):
        self.submit(READ)
        self.assertEqual(self.arm(fd=-1)[0], -errno.EBADF)
        self.assertEqual(self.arm(fd=1234567)[0], -errno.EBADF)
        self.assertEqual(self.tx.queue.count, 1)

    def test_input_epoch_must_advance(self):
        self.submit(READ)
        self.assertEqual(self.arm(epoch=0)[0], -errno.EINVAL)
        self.assertEqual(self.arm(epoch=1), (0, self.id, READ))
        self.assertEqual(self.issued(epoch=0), -errno.EINVAL)
        self.assertEqual(self.issued(epoch=2), -errno.ESTALE)

    def test_unissued_job_cannot_accept_modem_data(self):
        self.submit(READ)
        self.arm()
        self.assertEqual(self.feed("OK\r\n"), -errno.EPERM)
        self.assertEqual(self.tx.queue.acked, 0)
        self.assertEqual(self.issued(), 0)

    def test_fragmented_sms_list_empty_can_complete(self):
        self.begin(LIST)
        self.assertEqual(self.feed("O"), 0)
        self.assertEqual(self.feed("K\r"), 1)
        self.assertEqual(self.feed("\n"), COMPLETE)
        self.assertEqual(self.finish(), 0)
        self.assertEqual(self.tx.state, IDLE)

    def test_split_crlf_after_terminal_is_valid(self):
        self.begin(LIST)
        self.assertEqual(self.feed("OK\r"), COMPLETE)
        self.assertEqual(self.feed("\n\r\n"), COMPLETE)
        self.assertEqual(self.finish(), 0)

    def test_unexpected_trailing_bytes_in_later_read_poison_session(self):
        self.begin(LIST)
        self.assertEqual(self.feed("OK\r\n"), COMPLETE)
        self.assertEqual(self.feed("+CUSD:"), -errno.EPROTO)
        self.assertEqual(self.tx.state, QUARANTINED)

    def test_split_crlf_after_terminal_expires_if_delayed_too_long(self):
        self.begin(LIST)
        self.assertEqual(self.feed("OK\r"), COMPLETE)
        self.assertEqual(self.feed("\n", now=3000), -errno.ETIMEDOUT)
        self.assertEqual(self.tx.state, QUARANTINED)

    def test_sms_read_pdu_completes_and_wipes_frame(self):
        self.begin(READ)
        self.assertEqual(self.feed("+CMGR: 0,,2\r\n00"), 0)
        self.assertEqual(self.feed("0011\r\nOK\r\n"), 1)
        self.assertEqual(self.tx.queue.pdu_count, 1)
        self.assertEqual(self.finish(), 0)
        self.assertEqual(bytes(self.tx.frame.line), b"")
        self.assertEqual(self.tx.epoch, 1)

    def test_sms_notice_interleaves_without_completing_read(self):
        self.begin(READ)
        self.assertEqual(self.feed('+CMTI: "SM",3\r\n'), 0)
        self.assertEqual(self.feed("+CMGR: 0,,2\r\n000011\r\nOK\r\n"), 1)
        self.assertEqual(self.finish(), 0)

    def test_ussd_urc_after_ok(self):
        self.begin(USSD)
        self.assertEqual(self.feed("OK\r\n"), 0)
        self.assertEqual(self.finish(), -errno.EBUSY)
        self.assertEqual(self.feed('+CUSD: 0,"0041",72\r\n'), 1)
        self.assertEqual(self.finish(), 0)

    def test_ussd_urc_before_ok(self):
        self.begin(USSD)
        self.assertEqual(self.feed('+CUSD: 0,"0041",72\r\n'), 0)
        self.assertEqual(self.feed("OK\r\n"), 1)
        self.assertEqual(self.finish(), 0)

    def test_interactive_cannot_silently_finish(self):
        self.begin(USSD)
        self.assertEqual(self.feed('OK\r\n+CUSD: 1,"0041",72\r\n'), 2)
        self.assertEqual(self.tx.state, INTERACTIVE)
        self.assertEqual(self.finish(), -errno.EBUSY)
        self.assertEqual(self.issued(), -errno.EPERM)
        self.assertEqual(self.lib.veci_txn_abort(
            ctypes.byref(self.tx), 1, 123), -errno.ECANCELED)
        self.assertEqual(self.tx.state, QUARANTINED)

    def test_unexpected_cusd_during_sms_is_quarantined(self):
        self.begin(READ)
        self.assertEqual(self.feed('+CUSD: 0,"0041",72\r\n'), -errno.EPROTO)
        self.assertEqual(self.tx.state, QUARANTINED)

    def test_sms_read_header_during_ussd_is_quarantined(self):
        self.begin(USSD)
        self.assertEqual(self.feed("+CMGR: 0,,2\r\n"), -errno.EPROTO)
        self.assertEqual(self.tx.state, QUARANTINED)

    def test_trailing_new_response_after_ok_in_one_chunk_is_error(self):
        self.begin(LIST)
        self.assertEqual(self.feed("OK\r\nOK\r\n"), -errno.EPROTO)
        self.assertEqual(self.tx.state, QUARANTINED)
        self.assertEqual(self.finish(), -errno.EIO)

    def test_fragmented_trailing_incomplete_line_blocks_finalization(self):
        self.begin(LIST)
        self.assertEqual(self.feed("OK\r\nSTALE"), 1)
        self.assertEqual(self.finish(), -errno.EPROTO)
        self.assertEqual(self.tx.state, QUARANTINED)

    def test_parser_bad_sms_pdu_quarantines_queue(self):
        self.begin(READ)
        self.assertEqual(self.feed("+CMGR: 0,,2\r\nNOPE\r\n"), -errno.EPROTO)
        self.assertEqual(self.tx.state, QUARANTINED)

    def test_timeout_discards_all_pending_jobs(self):
        self.begin(USSD)
        self.assertEqual(self.submit(READ, ident=124), 0)
        self.assertEqual(self.feed("OK\r\n"), 0)
        self.assertEqual(self.lib.veci_txn_tick(
            ctypes.byref(self.tx), 3000), -errno.ETIMEDOUT)
        self.assertEqual(self.tx.queue.count, 0)
        self.assertEqual(self.tx.state, QUARANTINED)
        self.assertEqual(self.submit(READ, ident=125), -errno.EIO)

    def test_backward_clock_fails_closed(self):
        self.begin(USSD)
        self.assertEqual(self.feed("OK\r\n", now=999), -errno.EPROTO)
        self.assertEqual(self.tx.state, QUARANTINED)

    def test_external_fd_close_detected_before_feed(self):
        self.begin(USSD)
        self.fake_fd.close()
        self.assertEqual(self.feed("OK\r\n"), -errno.EBADF)
        self.assertEqual(self.tx.state, QUARANTINED)

    def test_old_epoch_or_wrong_job_never_feeds_current(self):
        self.begin(USSD)
        self.assertEqual(self.feed("OK\r\n", epoch=99), -errno.ESTALE)
        self.assertEqual(self.feed("OK\r\n", ident=124), -errno.ESTALE)
        self.assertEqual(self.tx.queue.acked, 0)
        self.assertEqual(self.feed("OK\r\n"), 0)

    def test_owner_stays_busy_until_application_finishes(self):
        self.begin(LIST)
        self.assertEqual(self.submit(READ, ident=124), 0)
        self.assertEqual(self.arm(epoch=2)[0], -errno.EBUSY)
        self.assertEqual(self.feed("OK\r\n"), 1)
        self.assertEqual(self.arm(epoch=2)[0], -errno.EBUSY)
        self.assertEqual(self.finish(), 0)
        self.epoch, self.id = 2, 124
        self.assertEqual(self.arm(), (0, 124, READ))
        self.assertEqual(self.issued(), 0)
        self.assertEqual(self.feed("+CMGR: 0,,2\r\n000011\r\nOK\r\n"), 1)
        self.assertEqual(self.finish(), 0)

    def test_no_hidden_reset_of_quarantine(self):
        self.begin(USSD)
        self.assertEqual(self.lib.veci_txn_abort(
            ctypes.byref(self.tx), 1, 123), -errno.ECANCELED)
        self.assertEqual(self.resync(2, confirmed=0), -errno.EACCES)
        self.assertEqual(self.resync(1, confirmed=1), -errno.EINVAL)
        self.assertEqual(self.resync(2, confirmed=1), 0)
        self.assertEqual(self.tx.state, IDLE)
        self.assertEqual(self.tx.queue.count, 0)
        self.assertEqual(self.submit(READ, ident=124), 0)
        self.epoch, self.id = 3, 124
        self.assertEqual(self.arm(), (0, 124, READ))

    def test_cannot_claim_resync_on_healthy_idle_state(self):
        self.assertEqual(self.resync(2, confirmed=1), -errno.EPERM)

    def test_no_os_device_io_in_transaction_coordinator(self):
        code = (SRC / "veci-modem-transaction.c").read_text()
        self.assertNotIn("AT+CM", code)
        self.assertNotIn("/dev/ttyUSB", code)
        for token in ("syslog(", "printf(", "socket(", "fopen(", "system(",
                      "write(", "read(", "exec(", "fork("):
            self.assertNotIn(token, code)


if __name__ == "__main__":
    unittest.main()
