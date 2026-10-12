"""Pure, host-only SMS-PDU/USSD framing tests. No modem or AT port access."""
import ctypes
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source/we5927-lte/src/veci-at-framing.c"

OTHER, OK, ERROR, SMS_PDU, SMS_NOTICE, USSD, PROTOCOL_ERROR = range(7)
WAITING, RESPONSE, INTERACTIVE, TERMINATED, FAILED = range(5)


class Frame(ctypes.Structure):
    _fields_ = [
        ("line", ctypes.c_char * 1024),
        ("line_len", ctypes.c_size_t),
        ("total", ctypes.c_size_t),
        ("pdu_expected", ctypes.c_int),
        ("failed", ctypes.c_int),
    ]


class Session(ctypes.Structure):
    _fields_ = [
        ("acked", ctypes.c_int),
        ("seen_urc", ctypes.c_int),
        ("mode", ctypes.c_int),
        ("failed", ctypes.c_int),
    ]


CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_char_p,
                            ctypes.c_int, ctypes.c_void_p)


class FramingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        cls.libpath = str(Path(cls.build.name) / "libveci-at-framing.so")
        p = subprocess.run(
            ["cc", "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
             "-fPIC", "-shared", str(SOURCE), "-o", cls.libpath],
            capture_output=True, text=True,
        )
        if p.returncode:
            raise AssertionError(p.stderr)
        cls.lib = ctypes.CDLL(cls.libpath)
        cls.lib.veci_frame_init.argtypes = [ctypes.POINTER(Frame)]
        cls.lib.veci_frame_feed.argtypes = [
            ctypes.POINTER(Frame), ctypes.c_char_p, ctypes.c_size_t,
            CALLBACK, ctypes.c_void_p,
        ]
        cls.lib.veci_frame_feed.restype = ctypes.c_int
        cls.lib.veci_frame_finish.argtypes = [
            ctypes.POINTER(Frame), CALLBACK, ctypes.c_void_p]
        cls.lib.veci_frame_finish.restype = ctypes.c_int
        cls.lib.veci_ussd_expire.argtypes = [ctypes.POINTER(Session)]
        cls.lib.veci_ussd_expire.restype = ctypes.c_int
        cls.lib.veci_ussd_init.argtypes = [ctypes.POINTER(Session)]
        cls.lib.veci_ussd_consume.argtypes = [
            ctypes.POINTER(Session), ctypes.c_int, ctypes.c_int]
        cls.lib.veci_ussd_consume.restype = ctypes.c_int

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.frame = Frame()
        self.lib.veci_frame_init(ctypes.byref(self.frame))
        self.events = []

        def collect(kind, value, metadata, _context):
            self.events.append((kind, value.decode("ascii"), metadata))
        self.callback = CALLBACK(collect)

    def feed(self, *pieces):
        result = 0
        for piece in pieces:
            if isinstance(piece, str):
                piece = piece.encode("ascii")
            result = self.lib.veci_frame_feed(
                ctypes.byref(self.frame), piece, len(piece),
                self.callback, None)
            if result:
                break
        return result

    def test_ordinary_terminal_lines_are_exact(self):
        self.assertEqual(self.feed(b"\r\nBOOKING\r\nO", b"K\r", b"\n"), 0)
        self.assertEqual([e[0] for e in self.events], [OTHER, OK])

    def test_sms_pdu_fragmented_at_arbitrary_read_boundaries(self):
        # SMSC length=0 octets, TPDU=2 octets; payload is deliberately synthetic.
        self.assertEqual(self.feed(
            "+CMGL: 1,0,,2\r\n00", "001", "1\r", "\nOK\r\n"), 0)
        self.assertEqual([e[0] for e in self.events], [OTHER, SMS_PDU, OK])
        self.assertEqual(self.events[1], (SMS_PDU, "000011", 2))

    def test_incoming_sms_notification_is_not_an_sms_body(self):
        self.feed('+CMTI: "SM",4\r\n')
        self.assertEqual(self.events[0][0], SMS_NOTICE)
        self.assertFalse(any(e[0] == SMS_PDU for e in self.events))

    def test_opaque_message_content_cannot_be_mistaken_for_terminal_ok(self):
        self.assertEqual(self.feed("+CMGR: 0,,2\r\nOK\r\n"), -1)
        self.assertEqual(self.events[-1][0], PROTOCOL_ERROR)
        self.assertFalse(any(e[0] == OK for e in self.events))

    def test_text_mode_sms_header_fails_closed(self):
        self.assertEqual(self.feed(
            '+CMGL: 1,"REC READ","+62812","","26/10/12,11:00:00+28"\r\n'), -1)
        self.assertEqual(self.events[-1][0], PROTOCOL_ERROR)

    def test_mismatched_tpdu_length_fails(self):
        self.assertEqual(self.feed("+CMGL: 2,0,,3\r\n000011\r\n"), -1)
        self.assertEqual(self.events[-1][0], PROTOCOL_ERROR)

    def test_non_hex_pdu_fails(self):
        self.assertEqual(self.feed("+CMT: ,2\r\n0000GG\r\n"), -1)
        self.assertEqual(self.events[-1][0], PROTOCOL_ERROR)

    def test_pdu_smsc_length_validated(self):
        self.assertEqual(self.feed("+CMGR: 0,,2\r\nFF0011\r\n"), -1)
        self.assertEqual(self.events[-1][0], PROTOCOL_ERROR)

    def test_error_terminals_are_not_success(self):
        self.feed("+CMS ERROR: 322\r\n")
        self.assertEqual(self.events[-1][0], ERROR)

    def test_async_ussd_can_arrive_after_ack(self):
        s = Session()
        self.lib.veci_ussd_init(ctypes.byref(s))
        self.feed("OK\r\n")
        state = self.lib.veci_ussd_consume(ctypes.byref(s), OK, 0)
        self.assertEqual(state, WAITING)
        self.feed('+CUSD: 0,"0053006900730061",72\r\n')
        self.assertEqual(self.events[-1][0], USSD)
        self.assertEqual(self.events[-1][2], 0)
        state = self.lib.veci_ussd_consume(ctypes.byref(s), USSD, 0)
        self.assertEqual(state, RESPONSE)

    def test_async_ussd_can_arrive_before_ack(self):
        s = Session()
        self.lib.veci_ussd_init(ctypes.byref(s))
        self.feed('+CUSD: 1,"0031",72\r\nOK\r\n')
        self.assertEqual(self.lib.veci_ussd_consume(
            ctypes.byref(s), USSD, 1), WAITING)
        self.assertEqual(self.lib.veci_ussd_consume(
            ctypes.byref(s), OK, 0), INTERACTIVE)

    def test_ussd_termination_does_not_automatically_retry(self):
        s = Session()
        self.lib.veci_ussd_init(ctypes.byref(s))
        self.assertEqual(self.lib.veci_ussd_consume(
            ctypes.byref(s), OK, 0), WAITING)
        self.assertEqual(self.lib.veci_ussd_consume(
            ctypes.byref(s), USSD, 2), TERMINATED)

    def test_ussd_error_remains_failed(self):
        s = Session()
        self.lib.veci_ussd_init(ctypes.byref(s))
        self.assertEqual(self.lib.veci_ussd_consume(
            ctypes.byref(s), ERROR, 0), FAILED)
        self.assertEqual(self.lib.veci_ussd_consume(
            ctypes.byref(s), OK, 0), FAILED)

    def test_invalid_ussd_mode_is_not_accepted(self):
        self.assertEqual(self.feed('+CUSD: 9,"any",15\r\n'), -1)
        self.assertEqual(self.events[-1][0], PROTOCOL_ERROR)

    def test_stream_budget_fails_closed(self):
        payload = b"X" * 1000 + b"\r\n"
        for _ in range(8):
            self.assertEqual(self.feed(payload), 0)
        self.assertEqual(self.feed(payload), -1)
        self.assertEqual(self.events[-1][0], PROTOCOL_ERROR)

    def test_line_budget_and_control_bytes_fail_closed(self):
        self.assertEqual(self.feed(b"A" * 1024), -1)
        self.lib.veci_frame_init(ctypes.byref(self.frame))
        self.events.clear()
        self.assertEqual(self.feed(b"OK\x00\r\n"), -1)
        self.assertEqual(self.events[-1][0], PROTOCOL_ERROR)

    def test_failed_parser_requires_explicit_reset(self):
        self.assertEqual(self.feed("BAD\x00"), -1)
        self.assertEqual(self.feed("OK\r\n"), -1)
        self.assertFalse(any(e[0] == OK for e in self.events))
        self.lib.veci_frame_init(ctypes.byref(self.frame))
        self.events.clear()
        self.assertEqual(self.feed("OK\r\n"), 0)
        self.assertEqual(self.events[-1][0], OK)

    def test_truncated_sms_pdu_fails_at_end_of_transaction(self):
        self.assertEqual(self.feed("+CMGL: 0,0,,2\r\n"), 0)
        self.assertEqual(self.lib.veci_frame_finish(
            ctypes.byref(self.frame), self.callback, None), -1)
        self.assertEqual(self.events[-1][0], PROTOCOL_ERROR)

    def test_partial_terminal_line_fails_at_end_of_transaction(self):
        self.assertEqual(self.feed("O"), 0)
        self.assertEqual(self.lib.veci_frame_finish(
            ctypes.byref(self.frame), self.callback, None), -1)
        self.assertFalse(any(e[0] == OK for e in self.events))

    def test_complete_response_can_finish(self):
        self.assertEqual(self.feed("OK\r\n"), 0)
        self.assertEqual(self.lib.veci_frame_finish(
            ctypes.byref(self.frame), self.callback, None), 0)

    def test_pending_ussd_can_be_expired_without_resend(self):
        s = Session()
        self.lib.veci_ussd_init(ctypes.byref(s))
        self.assertEqual(self.lib.veci_ussd_consume(
            ctypes.byref(s), OK, 0), WAITING)
        self.assertEqual(self.lib.veci_ussd_expire(
            ctypes.byref(s)), FAILED)
        self.assertEqual(self.lib.veci_ussd_consume(
            ctypes.byref(s), USSD, 0), FAILED)

    def test_no_modem_io_or_sensitive_logging_in_parser(self):
        src = SOURCE.read_text()
        for token in ("open(", "write(", "printf(", "syslog(", "AT+CMGS",
                      "AT+CUSD=1", "/dev/ttyUSB", "curl ", "wget "):
            self.assertNotIn(token, src)
        self.assertIn("VECI_FRAME_PDU_MAX 512", src)


if __name__ == "__main__":
    unittest.main()
