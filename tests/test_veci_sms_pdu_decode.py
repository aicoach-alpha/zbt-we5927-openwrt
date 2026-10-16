"""Real native C/host-only SMS-DELIVER PDU fixtures, never touch router.

Fixtures construct an SMSC + SMS-DELIVER TPDU, including septet packing,
UDH septet alignment, concat refs and UTF-16 big-endian, all offline.
"""
import ctypes
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source/we5927-lte/src/veci-sms-pdu-decode.c"


class Message(ctypes.Structure):
    _fields_ = [
        ("sender", ctypes.c_char * 24),
        ("text", ctypes.c_char * 1025),
        ("text_len", ctypes.c_size_t),
        ("alphabet", ctypes.c_uint),
        ("concat_ref", ctypes.c_uint),
        ("concat_total", ctypes.c_uint),
        ("concat_part", ctypes.c_uint),
        ("concat_is_16bit", ctypes.c_uint),
        ("udhi", ctypes.c_uint),
    ]


def pack_septets(codes, header=b""):
    # 3GPP UDH consumes ceil(header_octets*8 / 7) septets. Text begins
    # at that boundary, not immediately after the last UDH byte.
    header_septets = (len(header) * 8 + 6) // 7
    septets = header_septets + len(codes)
    buf = bytearray((septets * 7 + 7) // 8)
    buf[:len(header)] = header
    for i, code in enumerate(codes):
        bit = (header_septets + i) * 7
        for k in range(7):
            if code & (1 << k):
                buf[(bit + k) // 8] |= 1 << ((bit + k) % 8)
    return septets, bytes(buf)


def pdu(body=b"", *, sender="62812", dcs=0, udhi=False, udl=None,
        first_octet=None):
    if first_octet is None:
        first_octet = 0x40 if udhi else 0x00
    digits = sender + ("F" if len(sender) % 2 else "")
    addr = bytes(int(digits[k + 1] + digits[k], 16)
                 for k in range(0, len(digits), 2))
    if udl is None:
        udl = len(body)
    # SMSC len=0, FO, originator digit count, international TOA, address,
    # PID, DCS, dummy SCTS seven octets, UDL, user data.
    raw = (bytes([0, first_octet, len(sender), 0x91]) +
           addr + bytes([0, dcs]) + b"\x00" * 7 +
           bytes([udl]) + body)
    return raw.hex().upper()


def gsm7(text, *, header=b""):
    septets, octets = pack_septets([ord(c) for c in text], header)
    return pdu(octets, udl=septets, udhi=bool(header))


def ucs2(text, *, header=b""):
    octets = header + text.encode("utf-16-be")
    return pdu(octets, dcs=0x08, udhi=bool(header))


class NativePduDecoderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        cls.so = str(Path(cls.build.name) / "libveci-sms-pdu.so")
        result = subprocess.run(
            ["cc", "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
             "-fPIC", "-shared", str(SOURCE), "-o", cls.so],
            capture_output=True, text=True,
        )
        if result.returncode:
            raise AssertionError(result.stderr)
        cls.lib = ctypes.CDLL(cls.so)
        cls.lib.veci_sms_decode_deliver.argtypes = [
            ctypes.c_char_p, ctypes.POINTER(Message)]
        cls.lib.veci_sms_decode_deliver.restype = ctypes.c_int
        cls.lib.veci_sms_clear.argtypes = [ctypes.POINTER(Message)]

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def decode(self, encoded):
        output = Message()
        if isinstance(encoded, str):
            encoded = encoded.encode("ascii")
        status = self.lib.veci_sms_decode_deliver(encoded, ctypes.byref(output))
        return status, output

    def test_gsm7_plain_hello_and_sender(self):
        rc, m = self.decode(gsm7("HELLO"))
        self.assertEqual(rc, 0)
        self.assertEqual(m.sender, b"+62812")
        self.assertEqual(m.text, b"HELLO")
        self.assertEqual(m.text_len, 5)
        self.assertEqual(m.alphabet, 0)
        self.assertEqual(m.concat_total, 0)

    def test_ok_inside_sms_is_content_not_terminal(self):
        rc, m = self.decode(gsm7("OK"))
        self.assertEqual(rc, 0)
        self.assertEqual(m.text, b"OK")

    def test_gsm7_extension_and_non_ascii_alphabet(self):
        septets, octets = pack_septets([1, 5, 0, 27, 0x65])
        rc, m = self.decode(pdu(octets, udl=septets))
        self.assertEqual(rc, 0)
        self.assertEqual(m.text.decode(), "£é@€")

    def test_gsm7_udh_8bit_concat_alignment(self):
        udh = bytes([5, 0, 3, 0x7F, 2, 1])
        rc, m = self.decode(gsm7("HELLO", header=udh))
        self.assertEqual(rc, 0)
        self.assertEqual(m.text, b"HELLO")
        self.assertEqual((m.concat_ref, m.concat_total, m.concat_part),
                         (127, 2, 1))
        self.assertEqual(m.concat_is_16bit, 0)
        self.assertEqual(m.udhi, 1)

    def test_ucs2_bmp_and_surrogate_pair_to_utf8(self):
        rc, m = self.decode(ucs2("Halo €😀"))
        self.assertEqual(rc, 0)
        self.assertEqual(m.text.decode(), "Halo €😀")
        self.assertEqual(m.alphabet, 2)

    def test_ucs2_16bit_concat_metadata(self):
        udh = bytes([6, 8, 4, 0x12, 0x34, 2, 2])
        rc, m = self.decode(ucs2("Lanjut", header=udh))
        self.assertEqual(rc, 0)
        self.assertEqual(m.text.decode(), "Lanjut")
        self.assertEqual((m.concat_ref, m.concat_total, m.concat_part),
                         (0x1234, 2, 2))
        self.assertEqual(m.concat_is_16bit, 1)

    def test_ucs2_text_length_rejected_if_truncated(self):
        encoded = ucs2("ABC")
        rc, m = self.decode(encoded[:-2])
        self.assertEqual(rc, -1)
        self.assertEqual(m.text, b"")

    def test_odd_ucs2_length_rejected(self):
        rc, m = self.decode(pdu(b"\x00A\x00", dcs=8))
        self.assertEqual(rc, -1)
        self.assertEqual(m.text_len, 0)

    def test_isolated_high_surrogate_rejected(self):
        rc, _ = self.decode(pdu(b"\xD8\x00", dcs=8))
        self.assertEqual(rc, -1)

    def test_isolated_low_surrogate_rejected(self):
        rc, _ = self.decode(pdu(b"\xDC\x00", dcs=8))
        self.assertEqual(rc, -1)

    def test_unknown_8bit_and_compressed_dcs_rejected(self):
        for value in (4, 0x20, 0x0C, 0xF4):
            with self.subTest(dcs=value):
                rc, _ = self.decode(pdu(b"A", dcs=value))
                self.assertEqual(rc, -1)

    def test_sms_submit_pdu_is_not_sms_deliver(self):
        rc, _ = self.decode(pdu(b"A", first_octet=1))
        self.assertEqual(rc, -1)

    def test_malformed_hex_and_short_inputs_rejected(self):
        for value in ("", "00", "GGGG", "0", "0A0", "AB" * 257):
            with self.subTest(pdu=value[:12]):
                rc, m = self.decode(value)
                self.assertEqual(rc, -1)
                self.assertEqual(m.sender, b"")
                self.assertEqual(m.text, b"")

    def test_wrong_smsc_length_rejected(self):
        encoded = pdu(b"A", dcs=8)
        rc, _ = self.decode("FF" + encoded[2:])
        self.assertEqual(rc, -1)

    def test_bad_sender_digit_rejected(self):
        encoded = pdu(b"\x00H", dcs=8)
        # OA starts at bytes [4], flip a digit to B.
        raw = bytearray.fromhex(encoded)
        raw[4] = 0xB2
        rc, m = self.decode(raw.hex())
        self.assertEqual(rc, -1)
        self.assertEqual(m.text, b"")

    def test_bad_udh_concat_total_and_part_rejected(self):
        for header in (
            bytes([5, 0, 3, 7, 1, 1]),
            bytes([5, 0, 3, 7, 2, 3]),
            bytes([5, 0, 3, 7, 17, 2]),
        ):
            with self.subTest(header=header.hex()):
                rc, _ = self.decode(ucs2("A", header=header))
                self.assertEqual(rc, -1)

    def test_duplicate_concat_udh_rejected(self):
        header = bytes([10, 0, 3, 1, 2, 1, 0, 3, 1, 2, 1])
        rc, _ = self.decode(ucs2("X", header=header))
        self.assertEqual(rc, -1)

    def test_invalid_udh_ie_length_rejected(self):
        header = bytes([5, 0, 9, 1, 2, 3])
        rc, _ = self.decode(ucs2("X", header=header))
        self.assertEqual(rc, -1)

    def test_gsm7_dangling_escape_rejected(self):
        count, data = pack_septets([27])
        rc, m = self.decode(pdu(data, udl=count))
        self.assertEqual(rc, -1)
        self.assertEqual(m.text, b"")

    def test_gsm7_unsupported_extension_rejected(self):
        count, data = pack_septets([27, 2])
        rc, _ = self.decode(pdu(data, udl=count))
        self.assertEqual(rc, -1)

    def test_invalid_smsc_or_input_failure_zeroes_sensitive_buffer(self):
        rc, m = self.decode(ucs2("Temporary OTP 123456"))
        self.assertEqual(rc, 0)
        self.lib.veci_sms_clear(ctypes.byref(m))
        self.assertEqual(m.sender, b"")
        self.assertEqual(m.text, b"")
        self.assertEqual(m.text_len, 0)

    def test_no_runtime_dependency_logging_or_port_access(self):
        source = SOURCE.read_text()
        self.assertIn("secure_wipe(raw, sizeof(raw))", source)
        for forbidden in ("ttyUSB", "AT+CMGR", "AT+CMGL", "syslog(",
                          "printf(", "open(", "socket(", "system(", "curl "):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
