"""Strict one-slot +CMGR PDU parser and sensitive-memory hygiene, host-only."""
import ctypes
import errno
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"source/we5927-lte/src"

class Policy(ctypes.Structure):
    _fields_=[("session_binding",ctypes.c_uint64),
              ("request_nonce",ctypes.c_uint64),
              ("modem_generation",ctypes.c_uint64),
              ("slot",ctypes.c_uint),("state",ctypes.c_int)]

class AtFrame(ctypes.Structure):
    _fields_=[("line",ctypes.c_char*1024),
              ("line_len",ctypes.c_size_t),("total",ctypes.c_size_t),
              ("pdu_expected",ctypes.c_int),("failed",ctypes.c_int)]

class Cmgr(ctypes.Structure):
    _fields_=[("framing",AtFrame),("pdu",ctypes.c_char*513),
              ("binding",ctypes.c_uint64),("nonce",ctypes.c_uint64),
              ("generation",ctypes.c_uint64),("slot",ctypes.c_uint),
              ("status",ctypes.c_uint),("tpdu",ctypes.c_uint),
              ("stage",ctypes.c_uint),("echo_seen",ctypes.c_uint),
              ("completed",ctypes.c_uint),("failed",ctypes.c_uint)]

class Sms(ctypes.Structure):
    _fields_=[("sender",ctypes.c_char*24),("text",ctypes.c_char*1025),
              ("text_len",ctypes.c_size_t),
              ("alphabet",ctypes.c_uint),("concat_ref",ctypes.c_uint),
              ("concat_total",ctypes.c_uint),("concat_part",ctypes.c_uint),
              ("concat_is_16bit",ctypes.c_uint),("udhi",ctypes.c_uint)]

def fixture(text="HELLO",ucs2=False):
    if ucs2:
        body=text.encode("utf-16-be")
        udl=len(body)
        dcs=8
    else:
        septets=[ord(c) for c in text]
        body=bytearray((len(septets)*7+7)//8)
        for i,n in enumerate(septets):
            for k in range(7):
                if n & (1<<k):
                    shift=i*7+k
                    body[shift//8]|=1<<(shift%8)
        body=bytes(body)
        udl=len(septets)
        dcs=0
    # SMSC length 0, SMS-DELIVER, sender "62812", PID, DCS,
    # 7-byte dummy SCTS, then user-data length/body.
    payload=bytes([0,0,5,0x91,0x26,0x18,0xF2,0,dcs]) + b"\0"*7 + bytes([udl]) + body
    return payload.hex().upper(),len(payload)-1

class CMGRFrame(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.so=str(Path(cls.tmp.name)/"libcmgr.so")
        r=subprocess.run(["cc","-std=c99","-Wall","-Wextra","-Werror",
                          "-fPIC","-shared","-O2",
                          str(SRC/"veci-sms-cmgr-frame.c"),
                          str(SRC/"veci-at-framing.c"),
                          str(SRC/"veci-sms-pdu-decode.c"),
                          str(SRC/"veci-sms-read-slot-policy.c"),
                          "-o",cls.so],capture_output=True,text=True,timeout=20)
        if r.returncode: raise AssertionError(r.stderr)
        cls.lib=ctypes.CDLL(cls.so)
        cls.lib.veci_sms_read_arm.argtypes=[ctypes.POINTER(Policy),ctypes.c_uint,
            ctypes.c_uint64,ctypes.c_uint64,ctypes.c_uint64,
            ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int]
        cls.lib.veci_sms_read_arm.restype=ctypes.c_int
        cls.lib.veci_sms_read_issued.argtypes=[ctypes.POINTER(Policy),
            ctypes.c_uint64,ctypes.c_uint64,ctypes.c_uint64,ctypes.c_uint]
        cls.lib.veci_sms_read_issued.restype=ctypes.c_int
        cls.lib.veci_sms_read_complete.argtypes=[ctypes.POINTER(Policy),
            ctypes.c_uint64,ctypes.c_uint64,ctypes.c_uint64,ctypes.c_uint,ctypes.c_int]
        cls.lib.veci_sms_read_complete.restype=ctypes.c_int
        cls.lib.veci_sms_cmgr_init.argtypes=[ctypes.POINTER(Cmgr),ctypes.POINTER(Policy)]
        cls.lib.veci_sms_cmgr_init.restype=ctypes.c_int
        cls.lib.veci_sms_cmgr_feed.argtypes=[ctypes.POINTER(Cmgr),
                                             ctypes.c_void_p,ctypes.c_size_t]
        cls.lib.veci_sms_cmgr_feed.restype=ctypes.c_int
        cls.lib.veci_sms_cmgr_finish.argtypes=[ctypes.POINTER(Cmgr)]
        cls.lib.veci_sms_cmgr_finish.restype=ctypes.c_int
        cls.lib.veci_sms_cmgr_take.argtypes=[ctypes.POINTER(Cmgr),
                                             ctypes.POINTER(Policy),ctypes.POINTER(Sms)]
        cls.lib.veci_sms_cmgr_take.restype=ctypes.c_int
        cls.lib.veci_sms_cmgr_clear.argtypes=[ctypes.POINTER(Cmgr)]
        cls.lib.veci_sms_clear.argtypes=[ctypes.POINTER(Sms)]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.policy=Policy()
        self.rx=Cmgr()
        self.sms=Sms()
        self.slot=4
        self.session=111
        self.nonce=222
        self.generation=333
        self.assertEqual(self.lib.veci_sms_read_arm(ctypes.byref(self.policy),
            self.slot,self.session,self.nonce,self.generation,1,1,1,1,1),0)
        self.assertEqual(self.lib.veci_sms_read_issued(ctypes.byref(self.policy),
            self.session,self.nonce,self.generation,self.slot),0)
        self.assertEqual(self.lib.veci_sms_cmgr_init(ctypes.byref(self.rx),
            ctypes.byref(self.policy)),0)

    def feed(self,data):
        b=data if isinstance(data,bytes) else data.encode()
        backing=ctypes.create_string_buffer(b)
        return self.lib.veci_sms_cmgr_feed(ctypes.byref(self.rx),backing,len(b))

    def finish(self):
        return self.lib.veci_sms_cmgr_finish(ctypes.byref(self.rx))

    def completed(self):
        return self.lib.veci_sms_read_complete(ctypes.byref(self.policy),
            self.session,self.nonce,self.generation,self.slot,1)

    def take(self):
        return self.lib.veci_sms_cmgr_take(ctypes.byref(self.rx),
                  ctypes.byref(self.policy),ctypes.byref(self.sms))

    def msg(self,pdu=None,status=0,echo=True,ending="\r\nOK\r\n"):
        if pdu is None:pdu,length=fixture("OTP 1234")
        else:length=len(pdu)//2-1
        command=f"AT+CMGR={self.slot}\r\n" if echo else ""
        return (command+f"+CMGR: {status},,{length}\r\n"+pdu+ending).encode()

    def test_private_gsm7_only_after_full_ok(self):
        v=self.msg()
        for i in range(0,len(v),3):
            self.assertEqual(self.feed(v[i:i+3]),0)
        self.assertEqual(self.finish(),0)
        self.assertEqual(self.take(),-errno.EACCES)
        # Above rejected take securely wipes frame. Need a new authorized
        # request/nonce before text can be decoded.
        self.assertEqual(self.rx.nonce,0)

    def test_valid_full_gsm7_then_wipe_after_one_take(self):
        self.assertEqual(self.feed(self.msg()),0)
        self.assertEqual(self.finish(),0)
        self.assertEqual(self.completed(),0)
        self.assertEqual(self.take(),0)
        self.assertEqual(self.sms.text,b"OTP 1234")
        self.assertEqual(self.sms.sender,b"+62812")
        self.assertEqual(bytes(self.rx),bytes(ctypes.sizeof(Cmgr)))
        self.assertEqual(self.take(),-errno.EACCES)
        self.lib.veci_sms_clear(ctypes.byref(self.sms))
        self.assertEqual(bytes(self.sms),bytes(ctypes.sizeof(Sms)))

    def test_valid_ucs2(self):
        pdu,_=fixture("Halo €",ucs2=True)
        self.assertEqual(self.feed(self.msg(pdu=pdu,echo=False)),0)
        self.assertEqual(self.finish(),0)
        self.assertEqual(self.completed(),0)
        self.assertEqual(self.take(),0)
        self.assertEqual(self.sms.text.decode(), "Halo €")

    def test_missing_terminal_never_releases_pdu(self):
        partial=self.msg(ending="")
        self.assertEqual(self.feed(partial),0)
        self.assertNotEqual(self.finish(),0)
        self.assertEqual(self.take(),-errno.EACCES)

    def test_pdu_fragmentation_and_terminal_split(self):
        data=self.msg(ending="\r\nO")
        self.assertEqual(self.feed(data),0)
        self.assertEqual(self.feed("K\r"),0)
        self.assertEqual(self.feed("\n"),0)
        self.assertEqual(self.finish(),0)
        self.assertEqual(self.completed(),0)
        self.assertEqual(self.take(),0)

    def test_falsified_other_slot_echo_rejected(self):
        data=self.msg().replace(b"AT+CMGR=4",b"AT+CMGR=2",1)
        self.assertNotEqual(self.feed(data),0)
        self.assertEqual(self.rx.failed,1)

    def test_extra_pdu_or_cusd_poisoned(self):
        for suffix in (b"+CUSD: 0,\"0041\",72\r\n",b"+CMGL: 1,0,,2\r\n000011\r\n",
                       b"OK\r\n",b"+CMTI: \"ME\",1\r\n"):
            with self.subTest(suffix=suffix[:15]):
                self.lib.veci_sms_cmgr_clear(ctypes.byref(self.rx))
                self.assertEqual(self.lib.veci_sms_cmgr_init(ctypes.byref(self.rx),
                    ctypes.byref(self.policy)),0)
                self.assertNotEqual(self.feed(self.msg()+suffix),0)

    def test_malformed_binary_and_wrong_status_rejected(self):
        good_pdu, length = fixture("OTP 1234")
        wrong_len = self.msg().replace(
            f",,{length}\\r\\n".encode(), b",,240\\r\\n", 1)
        bad_hex = self.msg().replace(good_pdu.encode(), b"Z" + good_pdu[1:].encode(), 1)
        cases=(wrong_len,
               self.msg(status=8),
               bad_hex,
               b'AT+CMGL=4\\r\\n' + self.msg(echo=False))
        for payload in cases:
            self.lib.veci_sms_cmgr_clear(ctypes.byref(self.rx))
            self.assertEqual(self.lib.veci_sms_cmgr_init(ctypes.byref(self.rx),
                ctypes.byref(self.policy)),0)
            self.assertNotEqual(self.feed(payload),0)

    def test_incomplete_partial_bytes_fail_closed(self):
        pdu,n=fixture("HELLO")
        value=f"+CMGR: 0,,{n}\r\n{pdu}\r\nOK".encode()
        self.assertEqual(self.feed(value),0)
        self.assertNotEqual(self.finish(),0)

    def test_decoding_unsupported_alphabet_fails_and_wipes(self):
        pdu,_=fixture("HELLO")
        # Switch DCS from 0 to 0x04 (8-bit encoding); header still valid.
        raw=bytearray.fromhex(pdu)
        raw[8]=0x04
        self.assertEqual(self.feed(self.msg(raw.hex().upper())),0)
        self.assertEqual(self.finish(),0)
        self.assertEqual(self.completed(),0)
        self.assertNotEqual(self.take(),0)
        self.assertEqual(bytes(self.sms),bytes(ctypes.sizeof(Sms)))
        self.assertEqual(bytes(self.rx),bytes(ctypes.sizeof(Cmgr)))

    def test_reject_wrong_policy_binding(self):
        self.assertEqual(self.feed(self.msg()),0)
        self.assertEqual(self.finish(),0)
        self.assertEqual(self.completed(),0)
        self.policy.request_nonce+=1
        self.assertEqual(self.take(),-errno.EACCES)
        self.assertEqual(bytes(self.rx),bytes(ctypes.sizeof(Cmgr)))

    def test_limit_stream_to_8192(self):
        self.assertNotEqual(self.feed("X"*8193),0)
        self.assertEqual(self.rx.failed,1)

    def test_inert_source_no_at_transmission_or_persistence(self):
        code=(SRC/"veci-sms-cmgr-frame.c").read_text()
        for forbidden in ('write(', 'read(', 'open(', 'printf(', 'syslog(',
                          'fopen(', 'system(', 'AT+CMGS=', 'AT+CMGD='):
            self.assertNotIn(forbidden,code)
        mk=(ROOT/"source/we5927-lte/Makefile").read_text()
        self.assertNotIn("veci-sms-cmgr-frame.c",mk)
        self.assertNotIn("veci-sms-read-slot-policy.c",mk)

if __name__=="__main__":
    unittest.main()
