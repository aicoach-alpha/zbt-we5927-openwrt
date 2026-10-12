"""Offline C USSD +CUSD parser fixtures; no network, SIM, or modem commands."""
import ctypes
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source/we5927-lte/src/veci-ussd-decode.c"


class UssdReply(ctypes.Structure):
    _fields_ = [
        ("mode", ctypes.c_uint),
        ("dcs", ctypes.c_uint),
        ("decoded", ctypes.c_uint),
        ("text", ctypes.c_char * 1025),
        ("text_len", ctypes.c_size_t),
    ]


def ucs2_urc(value, mode=0, dcs=72):
    return f'+CUSD: {mode},"{value.encode("utf-16-be").hex().upper()}",{dcs}'


class UssdParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.so = str(Path(cls.tmp.name) / "libveci-ussd.so")
        p = subprocess.run(
            ["cc", "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
             "-fPIC", "-shared", str(SOURCE), "-o", cls.so],
            capture_output=True, text=True,
        )
        if p.returncode:
            raise AssertionError(p.stderr)
        cls.lib = ctypes.CDLL(cls.so)
        cls.lib.veci_ussd_decode_urc.argtypes = [
            ctypes.c_char_p, ctypes.POINTER(UssdReply)]
        cls.lib.veci_ussd_decode_urc.restype = ctypes.c_int
        cls.lib.veci_ussd_clear.argtypes = [ctypes.POINTER(UssdReply)]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def parse(self, line):
        o = UssdReply()
        if isinstance(line, str):
            line = line.encode("ascii")
        rc = self.lib.veci_ussd_decode_urc(line, ctypes.byref(o))
        return rc, o

    def test_ucs2_balances_quota_text(self):
        rc, value = self.parse(ucs2_urc("Sisa kuota: 5 GB"))
        self.assertEqual(rc, 0)
        self.assertEqual(value.mode, 0)
        self.assertEqual(value.dcs, 72)
        self.assertEqual(value.decoded, 1)
        self.assertEqual(value.text.decode(), "Sisa kuota: 5 GB")

    def test_unicode_surrogate_pair_and_currency_symbol(self):
        rc, value = self.parse(ucs2_urc("Rp 10.000 😀", mode=1, dcs=8))
        self.assertEqual(rc, 0)
        self.assertEqual(value.mode, 1)
        self.assertEqual(value.dcs, 8)
        self.assertEqual(value.text.decode(), "Rp 10.000 😀")

    def test_session_terminated_notification_without_text(self):
        rc, value = self.parse("+CUSD: 2")
        self.assertEqual(rc, 0)
        self.assertEqual(value.mode, 2)
        self.assertEqual(value.decoded, 1)
        self.assertEqual(value.text, b"")

    def test_ussd_network_unsupported_mode_4_is_structured(self):
        rc, value = self.parse("+CUSD: 4")
        self.assertEqual(rc, 0)
        self.assertEqual(value.mode, 4)

    def test_unknown_dcs_does_not_guess_plaintext(self):
        for dcs in (0, 15, 68, 255):
            with self.subTest(dcs=dcs):
                rc, value = self.parse(f'+CUSD: 0,"Your code is 123456",{dcs}')
                self.assertEqual(rc, 1)
                self.assertEqual(value.mode, 0)
                self.assertEqual(value.dcs, dcs)
                self.assertEqual(value.decoded, 0)
                self.assertEqual(value.text, b"")

    def test_reject_garbage_in_ucs2_hex(self):
        for payload in ("GGGG", "000", "000A0", "0053006Z"):
            with self.subTest(payload=payload):
                rc, value = self.parse(f'+CUSD: 0,"{payload}",72')
                self.assertEqual(rc, -1)
                self.assertEqual(value.text, b"")

    def test_reject_unpaired_high_surrogate(self):
        rc, _ = self.parse('+CUSD: 0,"D800",72')
        self.assertEqual(rc, -1)

    def test_reject_unpaired_low_surrogate(self):
        rc, _ = self.parse('+CUSD: 0,"DC00",72')
        self.assertEqual(rc, -1)

    def test_reject_broken_surrogate_pair(self):
        rc, _ = self.parse('+CUSD: 0,"D8000041",72')
        self.assertEqual(rc, -1)

    def test_reject_malformed_mode_and_missing_prefix(self):
        for line in ("OK", "+CUSD 0", "+CUSD: 6", "+CUSD: -1",
                     "+CUSD: 0x", "+CUSD: 00", "+CUSD: "):
            with self.subTest(line=line):
                rc, _ = self.parse(line)
                self.assertEqual(rc, -1)

    def test_reject_extra_fields_and_injection(self):
        for line in (
            '+CUSD: 0,"0041",72,10',
            '+CUSD: 0,"0041",72\nOK',
            '+CUSD: 0,"0041" ,72\r\n',
            '+CUSD: 0,"0041",',
            '+CUSD: 0,"0041"',
            '+CUSD: 0,0041,72',
            '+CUSD: 0,"0041",1000',
        ):
            with self.subTest(line=line[:20]):
                rc, _ = self.parse(line)
                self.assertEqual(rc, -1)

    def test_payload_over_512_is_rejected(self):
        rc, v = self.parse('+CUSD: 0,"' + "0041" * 129 + '",72')
        self.assertEqual(rc, -1)
        self.assertEqual(v.text, b"")

    def test_512_hex_chars_are_accepted(self):
        rc, v = self.parse('+CUSD: 0,"' + "0041" * 128 + '",72')
        self.assertEqual(rc, 0)
        self.assertEqual(v.text, b"A" * 128)

    def test_empty_ucs2_payload_decoded_as_empty(self):
        rc, v = self.parse('+CUSD: 0,"",72')
        self.assertEqual(rc, 0)
        self.assertEqual(v.text, b"")

    def test_explicit_wipe_of_transient_sensitive_data(self):
        rc, v = self.parse(ucs2_urc("OTP 123456"))
        self.assertEqual(rc, 0)
        self.lib.veci_ussd_clear(ctypes.byref(v))
        self.assertEqual(v.text_len, 0)
        self.assertEqual(v.text, b"")
        self.assertEqual(v.decoded, 0)

    def test_no_runtime_dependencies_or_logs(self):
        src = SOURCE.read_text()
        self.assertIn("wipe(payload, sizeof(payload))", src)
        for token in ("ttyUSB", "AT+CUSD=", "AT+CMGS=", "syslog(",
                      "printf(", "open(", "socket(", "system(", "curl "):
            self.assertNotIn(token, src)


if __name__ == "__main__":
    unittest.main()
