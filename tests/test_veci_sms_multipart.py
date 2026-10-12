"""Offline native C multipart SMS reassembly: bounded memory, SIM/scope isolation.

End-to-end exercises SMS-DELIVER PDU decode + assembler on the host only.
No modem, contacts, OTP, network access or real SMS.
"""
import ctypes
import errno
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_veci_sms_pdu_decode import Message, gsm7, ucs2

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "source/we5927-lte/src"


class Part(ctypes.Structure):
    _fields_ = [
        ("scope_id", ctypes.c_uint64),
        ("sender", ctypes.c_char_p),
        ("alphabet", ctypes.c_uint),
        ("concat_ref", ctypes.c_uint),
        ("concat_total", ctypes.c_uint),
        ("concat_part", ctypes.c_uint),
        ("concat_is_16bit", ctypes.c_uint),
        ("text", ctypes.c_char_p),
        ("text_len", ctypes.c_size_t),
    ]


class Group(ctypes.Structure):
    _fields_ = [
        ("scope_id", ctypes.c_uint64),
        ("opened_ms", ctypes.c_int64),
        ("ref", ctypes.c_uint),
        ("total", ctypes.c_uint),
        ("alphabet", ctypes.c_uint),
        ("ref_16bit", ctypes.c_uint),
        ("received", ctypes.c_uint),
        ("occupied", ctypes.c_uint),
        ("completed", ctypes.c_uint),
        ("sender", ctypes.c_char * 24),
        ("mask", ctypes.c_uint),
        ("len", ctypes.c_uint16 * 8),
        ("chunks", (ctypes.c_char * 513) * 8),
    ]


class State(ctypes.Structure):
    _fields_ = [
        ("groups", Group * 2),
        ("last_now_ms", ctypes.c_int64),
        ("clock_valid", ctypes.c_int),
        ("poisoned", ctypes.c_int),
    ]


class Result(ctypes.Structure):
    _fields_ = [
        ("text", ctypes.c_char * 2049),
        ("text_len", ctypes.c_size_t),
        ("scope_id", ctypes.c_uint64),
        ("total_parts", ctypes.c_uint),
    ]


class MultipartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.so = str(Path(cls.tmp.name) / "libveci-mp.so")
        p = subprocess.run([
            "cc", "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
            "-fPIC", "-shared",
            str(SRC / "veci-sms-multipart.c"),
            str(SRC / "veci-sms-pdu-decode.c"),
            "-o", cls.so
        ], capture_output=True, text=True)
        if p.returncode:
            raise AssertionError(p.stderr)
        cls.lib = ctypes.CDLL(cls.so)
        cls.lib.veci_mp_reset.argtypes = [ctypes.POINTER(State)]
        cls.lib.veci_mp_clear_result.argtypes = [ctypes.POINTER(Result)]
        cls.lib.veci_mp_expire.argtypes = [ctypes.POINTER(State), ctypes.c_int64]
        cls.lib.veci_mp_expire.restype = ctypes.c_int
        cls.lib.veci_mp_add.argtypes = [
            ctypes.POINTER(State), ctypes.POINTER(Part), ctypes.c_int64,
            ctypes.POINTER(Result)]
        cls.lib.veci_mp_add.restype = ctypes.c_int
        cls.lib.veci_sms_decode_deliver.argtypes = [
            ctypes.c_char_p, ctypes.POINTER(Message)]
        cls.lib.veci_sms_decode_deliver.restype = ctypes.c_int

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.s = State()
        self.o = Result()
        self.lib.veci_mp_reset(ctypes.byref(self.s))
        self.now = 1000

    def add(self, text="Hi", seq=1, total=2, ref=8, scope=11,
            sender=b"+62812", alphabet=0, is16=0, now=None):
        if now is None:
            now = self.now
        text = text.encode("utf-8") if isinstance(text, str) else text
        p = Part(scope, sender, alphabet, ref, total, seq, is16, text, len(text))
        return self.lib.veci_mp_add(
            ctypes.byref(self.s), ctypes.byref(p), now, ctypes.byref(self.o))

    def test_in_order_multipart_joins_without_extra_characters(self):
        self.assertEqual(self.add("Halo "), 0)
        self.assertEqual(self.add("Indonesia", seq=2), 1)
        self.assertEqual(self.o.text.decode(), "Halo Indonesia")
        self.assertEqual(self.o.total_parts, 2)
        self.assertEqual(self.o.scope_id, 11)

    def test_out_of_order_part_delivery(self):
        self.assertEqual(self.add("Dunia", seq=2), 0)
        self.assertEqual(self.add("Halo ", seq=1), 1)
        self.assertEqual(self.o.text, b"Halo Dunia")

    def test_three_segments_with_unicode(self):
        self.assertEqual(self.add("Selamat ", total=3, alphabet=2), 0)
        self.assertEqual(self.add("pagi 🌄", seq=3, total=3, alphabet=2), 0)
        self.assertEqual(self.add("semua, ", seq=2, total=3, alphabet=2), 1)
        self.assertEqual(self.o.text.decode(), "Selamat semua, pagi 🌄")

    def test_scope_id_prevents_cross_sim_mix(self):
        self.add("SIM1-", scope=101)
        self.add("SIM2-", scope=202)
        self.assertEqual(self.add("Part2", seq=2, scope=101), 1)
        self.assertEqual(self.o.text, b"SIM1-Part2")
        self.assertEqual(self.add("Done", seq=2, scope=202), 1)
        self.assertEqual(self.o.text, b"SIM2-Done")

    def test_two_different_senders_same_ref_do_not_mix(self):
        self.add("A", sender=b"+62801")
        self.add("B", sender=b"+62802")
        self.assertEqual(self.add("1", seq=2, sender=b"+62801"), 1)
        self.assertEqual(self.o.text, b"A1")
        self.assertEqual(self.add("2", seq=2, sender=b"+62802"), 1)
        self.assertEqual(self.o.text, b"B2")

    def test_same_sender_different_reference_full_capacity(self):
        self.add("A", ref=10)
        self.add("B", ref=11)
        self.assertEqual(self.add("C", ref=12), -errno.ENOSPC)
        self.assertFalse(self.s.poisoned)

    def test_exact_duplicate_part_is_idempotent(self):
        self.add("A")
        self.assertEqual(self.add("A"), 0)
        self.assertEqual(self.s.groups[0].received, 1)
        self.assertEqual(self.add("B", seq=2), 1)

    def test_conflicting_duplicate_poison_and_erase(self):
        self.add("A")
        self.assertEqual(self.add("DIFFERENT"), -errno.EPROTO)
        self.assertEqual(self.s.poisoned, 1)
        self.assertEqual(self.add("B", seq=2), -errno.EIO)
        self.assertEqual(self.s.groups[0].chunks[0].raw, b"\x00" * 513)

    def test_total_change_same_sender_ref_rejected(self):
        self.add("A", total=2)
        self.assertEqual(self.add("B", total=3, seq=2), -errno.EPROTO)
        self.assertTrue(self.s.poisoned)

    def test_alphabet_change_same_sender_ref_rejected(self):
        self.add("A", alphabet=0)
        self.assertEqual(self.add("B", alphabet=2, seq=2), -errno.EPROTO)

    def test_completed_group_is_tombstoned_until_ttl(self):
        self.add("A")
        self.add("B", seq=2)
        self.assertEqual(self.add("A", now=2000), -errno.EALREADY)
        self.assertEqual(self.lib.veci_mp_expire(ctypes.byref(self.s), 601000), 0)
        self.assertEqual(self.add("Fresh", now=601000), 0)

    def test_timeout_of_incomplete_group_fails_closed(self):
        self.add("Unfinished")
        self.assertEqual(self.lib.veci_mp_expire(
            ctypes.byref(self.s), 601000), -errno.ETIMEDOUT)
        self.assertEqual(self.s.poisoned, 1)
        self.assertEqual(self.add("Again", now=601001), -errno.EIO)
        self.lib.veci_mp_reset(ctypes.byref(self.s))
        self.assertEqual(self.add("New", now=601002), 0)

    def test_clock_regression_erases_buffers(self):
        self.add("Secret", now=2000)
        self.assertEqual(self.add("B", seq=2, now=1999), -errno.EPROTO)
        self.assertEqual(self.s.poisoned, 1)
        self.assertEqual(self.s.groups[0].chunks[0].raw, b"\x00" * 513)

    def test_invalid_input_cannot_create_group(self):
        for kwargs in (
            {"scope": 0}, {"sender": b""}, {"sender": b"+62ABC"},
            {"seq": 0}, {"seq": 3}, {"total": 1},
            {"total": 9}, {"ref": 256}, {"ref": 65536, "is16": 1},
            {"alphabet": 1}, {"is16": 2},
        ):
            with self.subTest(kwargs=kwargs):
                self.assertEqual(self.add("A", **kwargs), -errno.EINVAL)
                self.assertEqual(self.s.groups[0].occupied, 0)

    def test_utf8_rejects_null_overlong_and_surrogate(self):
        for x in (b"A\x00B", b"\xc0\xaf", b"\xed\xa0\x80",
                  b"\xf4\x90\x80\x80", b"\xe2\x82", b"\xff"):
            with self.subTest(data=x):
                self.assertEqual(self.add(x), -errno.EINVAL)

    def test_clear_result_removes_text(self):
        self.add("Hidden ")
        self.add("OTP", seq=2)
        self.lib.veci_mp_clear_result(ctypes.byref(self.o))
        self.assertEqual(self.o.text, b"")
        self.assertEqual(self.o.text_len, 0)
        self.assertEqual(self.o.scope_id, 0)

    def test_full_reset_removes_state_and_tombstones(self):
        self.add("Sensitive")
        self.lib.veci_mp_reset(ctypes.byref(self.s))
        self.assertEqual(self.s.groups[0].sender, b"")
        self.assertEqual(self.s.groups[0].chunks[0].raw, b"\x00" * 513)
        self.assertEqual(self.s.clock_valid, 0)

    def test_end_to_end_gsm7_pdu_decode_and_assemble(self):
        for seq, text in ((2, "Dunia"), (1, "Halo ")):
            header = bytes([5, 0, 3, 77, 2, seq])
            m = Message()
            raw = gsm7(text, header=header)
            self.assertEqual(self.lib.veci_sms_decode_deliver(
                raw.encode("ascii"), ctypes.byref(m)), 0)
            self.assertEqual((m.concat_ref, m.concat_total, m.concat_part),
                             (77, 2, seq))
            self.assertEqual(self.add(
                m.text.decode("utf-8"), seq=m.concat_part,
                total=m.concat_total, ref=m.concat_ref,
                sender=m.sender, alphabet=m.alphabet,
                is16=m.concat_is_16bit), 1 if seq == 1 else 0)
        self.assertEqual(self.o.text, b"Halo Dunia")

    def test_end_to_end_ucs2_16bit_concat(self):
        for seq, text in ((1, "Jalan "), (2, "pagi 🚴")):
            header = bytes([6, 8, 4, 0x12, 0x34, 2, seq])
            m = Message()
            self.assertEqual(self.lib.veci_sms_decode_deliver(
                ucs2(text, header=header).encode(), ctypes.byref(m)), 0)
            self.assertEqual(self.add(
                m.text.decode(), seq=m.concat_part, total=m.concat_total,
                ref=m.concat_ref, sender=m.sender,
                alphabet=m.alphabet, is16=m.concat_is_16bit),
                1 if seq == 2 else 0)
        self.assertEqual(self.o.text.decode(), "Jalan pagi 🚴")

    def test_no_io_or_external_dependencies(self):
        code = (SRC / "veci-sms-multipart.c").read_text()
        for token in ("ttyUSB", "AT+CMGS", "syslog(", "printf(",
                      "open(", "socket(", "system(", "malloc(", "free("):
            self.assertNotIn(token, code)


if __name__ == "__main__":
    unittest.main()
