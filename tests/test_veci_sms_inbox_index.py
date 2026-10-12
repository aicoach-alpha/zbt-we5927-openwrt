"""Source-only SMS PDU inbox index parser, host tests, NO modem/OTP access."""
import ctypes
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "source/we5927-lte/src"
ENTRY = SRC / "veci-sms-inbox-index.c"
HEADER = SRC / "veci-sms-inbox-index.h"
FRAME = SRC / "veci-at-framing.c"


class SmsEntry(ctypes.Structure):
    _fields_ = [("index", ctypes.c_uint32),
                ("state", ctypes.c_uint32),
                ("tpdu_octets", ctypes.c_uint32)]


def cmgl(index, state=0, tpdu="000011"):
    # Hex 00 = SMSC length 0, 0011 = exactly two TPDU octets.
    assert len(tpdu) >= 4 and len(tpdu) % 2 == 0
    return f"+CMGL: {index},{state},,{len(tpdu)//2-1}\r\n{tpdu}\r\n"


class InboxIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        output = Path(cls.temp.name) / "libveci-inbox.so"
        r = subprocess.run(
            ["cc", "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
             "-fPIC", "-shared", str(FRAME), str(ENTRY), "-o", str(output)],
            capture_output=True, text=True)
        if r.returncode:
            raise AssertionError(r.stderr)
        cls.lib = ctypes.CDLL(str(output))
        cls.lib.veci_sms_index_init.argtypes = [ctypes.c_void_p, ctypes.c_int]
        cls.lib.veci_sms_index_init.restype = ctypes.c_int
        cls.lib.veci_sms_index_feed.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]
        cls.lib.veci_sms_index_feed.restype = ctypes.c_int
        cls.lib.veci_sms_index_finish.argtypes = [ctypes.c_void_p]
        cls.lib.veci_sms_index_finish.restype = ctypes.c_int
        cls.lib.veci_sms_index_count.argtypes = [ctypes.c_void_p]
        cls.lib.veci_sms_index_count.restype = ctypes.c_int
        cls.lib.veci_sms_index_get.argtypes = [
            ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(SmsEntry)]
        cls.lib.veci_sms_index_get.restype = ctypes.c_int
        cls.lib.veci_sms_index_clear.argtypes = [ctypes.c_void_p]

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.session = ctypes.create_string_buffer(16384)
        self.assertEqual(self.lib.veci_sms_index_init(self.session, 1), 0)

    def feed(self, stream, fragments=0):
        if isinstance(stream, str):
            stream = stream.encode("ascii")
        if not fragments:
            return self.lib.veci_sms_index_feed(self.session, stream, len(stream))
        for i in range(0, len(stream), fragments):
            part = stream[i:i+fragments]
            result = self.lib.veci_sms_index_feed(self.session, part, len(part))
            if result:
                return result
        return 0

    def items(self):
        n = self.lib.veci_sms_index_count(self.session)
        if n < 0:
            return None
        arr = []
        for i in range(n):
            result = SmsEntry()
            self.assertEqual(self.lib.veci_sms_index_get(
                self.session, i, ctypes.byref(result)), 0)
            arr.append((result.index, result.state, result.tpdu_octets))
        return arr

    def test_offline_compiles_with_no_firmware_link(self):
        mk = (ROOT / "source/we5927-lte/Makefile").read_text()
        self.assertNotIn("veci-sms-inbox-index.c", mk)
        src = ENTRY.read_text()
        for not_allowed in ("/dev/", "sysupgrade", "AT+CMGS", "AT+CMGR",
                            "AT+CMGD", "AT+CUSD=", "printf(", "syslog(",
                            "fopen(", "open(", "socket("):
            self.assertNotIn(not_allowed, src)
        self.assertIn("approved != 1", src)

    def test_exact_approval_required_before_processing(self):
        for flag in (0, 2, -1):
            self.assertLess(self.lib.veci_sms_index_init(self.session, flag), 0)
            self.assertLess(self.feed(cmgl(1) + "OK\r\n"), 0)
            self.assertIsNone(self.items())
        self.assertEqual(self.lib.veci_sms_index_init(self.session, 1), 0)

    def test_empty_inbox_only_after_real_terminal_ok(self):
        self.assertEqual(self.feed("OK\r\n"), 0)
        self.assertIsNone(self.items())
        self.assertEqual(self.lib.veci_sms_index_finish(self.session), 0)
        self.assertEqual(self.items(), [])

    def test_two_headers_pdus_and_fragmentation(self):
        for piece in (1, 2, 5, 23):
            with self.subTest(fragment=piece):
                self.lib.veci_sms_index_init(self.session, 1)
                wire = "AT+CMGL=4\r\n" + cmgl(1, 0) + cmgl(3, 1) + "OK\r\n"
                self.assertEqual(self.feed(wire, piece), 0)
                self.assertEqual(self.lib.veci_sms_index_finish(self.session), 0)
                self.assertEqual(self.items(), [(1,0,2), (3,1,2)])

    def test_metadata_not_available_midstream(self):
        self.assertEqual(self.feed(cmgl(1)), 0)
        self.assertIsNone(self.items())
        self.assertLess(self.lib.veci_sms_index_finish(self.session), 0)
        self.assertIsNone(self.items())

    def test_legacy_pdu_header_status_four_allowed(self):
        self.assertEqual(self.feed(cmgl(65535, 4) + "OK\r\n"), 0)
        self.assertEqual(self.lib.veci_sms_index_finish(self.session), 0)
        self.assertEqual(self.items(), [(65535, 4, 2)])

    def test_duplicate_index_poison_and_wipe(self):
        self.assertLess(self.feed(cmgl(2) + cmgl(2) + "OK\r\n"), 0)
        self.assertIsNone(self.items())
        self.assertLess(self.feed(cmgl(3) + "OK\r\n"), 0)

    def test_synthetic_sms_text_not_retained_or_exposed(self):
        # Unlike header text-mode parsing, PDU bytes may themselves
        # contain a sensitive token. The parser never returns it.
        msg = cmgl(1, 0, "004F5450303939")
        self.assertEqual(self.feed(msg + "OK\r\n"), 0)
        self.assertEqual(self.lib.veci_sms_index_finish(self.session), 0)
        self.assertEqual(self.items(), [(1,0,6)])
        self.assertNotIn(b"4F5450303939", self.session.raw)
        self.assertNotIn(b"OTP099", self.session.raw)
        self.lib.veci_sms_index_clear(self.session)
        self.assertFalse(any(self.session.raw))

    def test_text_mode_sms_rejected(self):
        payload = '+CMGL: 1,"REC READ","+62812","","26/10/12,11:00"\r\n'
        self.assertLess(self.feed(payload), 0)
        self.assertIsNone(self.items())

    def test_malformed_header_and_oversize_numeric_rejected(self):
        for item in ("+CMGL: 1,0,22", "+CMGL: 1,0,,0",
                     "+CMGL: 1,0,,241", "+CMGL: 1,5,,2",
                     "+CMGL: 70000,0,,2", "+CMGL: -1,0,,2",
                     "+CMGL: 1,0,,2,1", "+CMGL: 1,0,,2X",
                     "+CMGL: 1,0,\"X\",2"):
            with self.subTest(item=item):
                self.lib.veci_sms_index_init(self.session, 1)
                self.assertLess(self.feed(item+"\r\n"), 0)
                self.assertIsNone(self.items())

    def test_pdu_mismatch_or_nonhex_poison(self):
        for wire in (cmgl(1, 0, "000011")[:-4] + "GG\r\nOK\r\n",
                     "+CMGL: 1,0,,4\r\n000011\r\nOK\r\n",
                     "+CMGL: 1,0,,2\r\nFF0011\r\nOK\r\n"):
            with self.subTest(wire=wire[:20]):
                self.lib.veci_sms_index_init(self.session, 1)
                self.assertLess(self.feed(wire), 0)
                self.assertIsNone(self.items())

    def test_unexpected_urc_and_usdd_rejected(self):
        for wire in ('+CMTI: "SM",3\r\nOK\r\n',
                     '+CUSD: 0,"0031",72\r\nOK\r\n',
                     '+CMT: ,2\r\n000011\r\nOK\r\n',
                     '+CMS ERROR: 500\r\n'):
            with self.subTest(wire=wire[:12]):
                self.lib.veci_sms_index_init(self.session, 1)
                self.assertLess(self.feed(wire), 0)
                self.assertIsNone(self.items())

    def test_truncated_mid_header_and_pdu(self):
        for wire in ("+CMGL: 1,0,,2\r\n", "OK", "+CMGL: 1,0,,2\r\n0000"):
            self.lib.veci_sms_index_init(self.session, 1)
            self.assertEqual(self.feed(wire), 0)
            self.assertLess(self.lib.veci_sms_index_finish(self.session), 0)
            self.assertIsNone(self.items())

    def test_post_terminal_data_rejected(self):
        self.assertLess(self.feed(cmgl(1) + "OK\r\nLATE\r\n"), 0)
        self.assertIsNone(self.items())
        self.lib.veci_sms_index_init(self.session, 1)
        self.assertEqual(self.feed("OK\r\n"), 0)
        self.assertLess(self.feed(cmgl(1)), 0)
        self.assertIsNone(self.items())

    def test_index_list_bounded_by_16_and_no_partial_commit(self):
        self.assertEqual(self.feed("".join(cmgl(i) for i in range(16))+"OK\r\n"), 0)
        self.assertEqual(self.lib.veci_sms_index_finish(self.session), 0)
        self.assertEqual(len(self.items()),16)
        self.lib.veci_sms_index_init(self.session,1)
        self.assertLess(self.feed("".join(cmgl(i) for i in range(17))+"OK\r\n"), 0)
        self.assertIsNone(self.items())

    def test_error_after_valid_message_leaks_nothing(self):
        self.assertLess(self.feed(cmgl(1)+"ERROR\r\n"), 0)
        self.assertIsNone(self.items())
        self.assertNotIn(b"000011", self.session.raw)

    def test_get_rejects_invalid_ordinal_or_incomplete(self):
        output = SmsEntry(123, 123, 123)
        self.assertLess(self.lib.veci_sms_index_get(self.session,0,ctypes.byref(output)),0)
        self.assertEqual((output.index,output.state,output.tpdu_octets),(0,0,0))
        self.assertEqual(self.feed(cmgl(5)+"OK\r\n"), 0)
        self.assertEqual(self.lib.veci_sms_index_finish(self.session),0)
        self.assertLess(self.lib.veci_sms_index_get(self.session,7,ctypes.byref(output)),0)
        self.assertEqual((output.index,output.state,output.tpdu_octets),(0,0,0))


if __name__ == "__main__":
    unittest.main()
