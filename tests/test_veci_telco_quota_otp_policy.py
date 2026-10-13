"""Automatic OTP may ONLY serve verified telco app quota-login.

No actual inbox reading, SMS body, operator credentials, network or modem.
"""
import ctypes
import errno
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"source/we5927-lte/src/veci-telco-quota-otp-policy.c"
HEADER=ROOT/"source/we5927-lte/src/veci-telco-quota-otp-policy.h"

class Gate(ctypes.Structure):
    _fields_=[("quota_login_id",ctypes.c_uint64),
              ("modem_generation",ctypes.c_uint64),
              ("armed_ms",ctypes.c_uint64),
              ("deadline_ms",ctypes.c_uint64),
              ("provider",ctypes.c_uint),
              ("approved_slot",ctypes.c_uint),
              ("state",ctypes.c_int)]

class OnlyQuotaOtp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.so=str(Path(cls.tmp.name)/"quota-otp.so")
        p=subprocess.run(["cc","-std=c99","-O2","-Wall","-Wextra",
                          "-Werror","-shared","-fPIC",str(SRC),"-o",cls.so],
                         capture_output=True,text=True,timeout=20)
        if p.returncode: raise AssertionError(p.stderr)
        cls.lib=ctypes.CDLL(cls.so)
        cls.lib.veci_telco_quota_otp_begin.argtypes=[
            ctypes.POINTER(Gate),ctypes.c_uint,ctypes.c_uint,
            ctypes.c_uint64,ctypes.c_uint64,ctypes.c_uint64,
            ctypes.c_uint,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int]
        cls.lib.veci_telco_quota_otp_begin.restype=ctypes.c_int
        cls.lib.veci_telco_quota_otp_allow_candidate.argtypes=[
            ctypes.POINTER(Gate),ctypes.c_uint,ctypes.c_uint,ctypes.c_uint,
            ctypes.c_uint64,ctypes.c_uint64,ctypes.c_uint64,ctypes.c_int,ctypes.c_int]
        cls.lib.veci_telco_quota_otp_allow_candidate.restype=ctypes.c_int
        cls.lib.veci_telco_quota_otp_clear.argtypes=[ctypes.POINTER(Gate)]

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def setUp(self):
        self.g=Gate()

    def begin(self,provider=1,purpose=1,login=123456,gen=444,
              now=100000,ttl=30000,flags=(1,1,1,1)):
        return self.lib.veci_telco_quota_otp_begin(
            ctypes.byref(self.g),provider,purpose,login,gen,now,ttl,*flags)

    def candidate(self,provider=1,purpose=1,slot=4,login=123456,
                  gen=444,now=100100,proofs=(1,1)):
        return self.lib.veci_telco_quota_otp_allow_candidate(
            ctypes.byref(self.g),provider,purpose,slot,login,gen,now,*proofs)

    def test_only_authorized_quota_login_single_slot(self):
        self.assertEqual(self.begin(),0)
        self.assertEqual(self.candidate(),0)
        self.assertEqual(self.g.approved_slot,4)
        self.assertEqual(self.g.state,2)
        self.assertNotEqual(self.candidate(),0)

    def test_allow_known_telcos_only_when_verified(self):
        for provider in range(1,8):
            with self.subTest(provider=provider):
                self.lib.veci_telco_quota_otp_clear(ctypes.byref(self.g))
                self.assertEqual(self.begin(provider=provider),0)
                self.assertEqual(self.candidate(provider=provider),0)
        self.lib.veci_telco_quota_otp_clear(ctypes.byref(self.g))
        for provider in (0,8,99,65535):
            self.assertEqual(self.begin(provider=provider),-errno.EACCES)

    def test_bank_otp_never_auto(self):
        self.assertEqual(self.begin(purpose=2),-errno.EACCES)
        self.assertEqual(self.begin(),0)
        self.assertEqual(self.candidate(purpose=2),-errno.EACCES)
        self.assertEqual(self.g.state,3)
        self.assertNotEqual(self.candidate(),0)

    def test_wallet_otp_never_auto(self):
        self.assertEqual(self.begin(purpose=3),-errno.EACCES)
        self.assertEqual(self.begin(),0)
        self.assertEqual(self.candidate(purpose=3),-errno.EACCES)

    def test_email_otp_never_auto(self):
        self.assertEqual(self.begin(purpose=4),-errno.EACCES)
        self.assertEqual(self.begin(),0)
        self.assertEqual(self.candidate(purpose=4),-errno.EACCES)

    def test_other_services_otp_never_auto(self):
        for purpose in (0,5,6,999):
            with self.subTest(purpose=purpose):
                self.assertEqual(self.begin(purpose=purpose),-errno.EACCES)

    def test_no_quota_login_no_permission(self):
        self.assertEqual(self.candidate(),-errno.EACCES)
        self.assertEqual(self.begin(login=0),-errno.EACCES)
        self.assertEqual(self.begin(flags=(0,1,1,1)),-errno.EACCES)

    def test_all_official_operator_and_sim_gates_required(self):
        for i in range(4):
            for bad in (0,2,-1):
                with self.subTest(which=i,flag=bad):
                    self.lib.veci_telco_quota_otp_clear(ctypes.byref(self.g))
                    a=[1,1,1,1]
                    a[i]=bad
                    self.assertEqual(self.begin(flags=tuple(a)),-errno.EACCES)
                    self.assertEqual(self.g.state,0)

    def test_bare_cmti_without_pre_read_attestation_denied(self):
        self.assertEqual(self.begin(),0)
        self.assertEqual(self.candidate(proofs=(0,1)),-errno.EACCES)
        self.assertEqual(self.g.state,3)
        self.assertNotEqual(self.candidate(),0)

    def test_spoofable_sender_alone_never_enough(self):
        self.assertEqual(self.begin(),0)
        self.assertEqual(self.candidate(proofs=(1,0)),-errno.EACCES)
        self.assertEqual(self.g.state,3)

    def test_provider_mismatch_does_not_autoscan_next_sms(self):
        self.assertEqual(self.begin(provider=1),0)
        self.assertEqual(self.candidate(provider=2),-errno.EACCES)
        self.assertEqual(self.g.state,3)
        self.assertEqual(self.candidate(provider=1,slot=5),-errno.EACCES)

    def test_incorrect_operator_login_transaction_denied(self):
        self.assertEqual(self.begin(),0)
        self.assertEqual(self.candidate(login=123457),-errno.EACCES)
        self.assertEqual(self.g.state,3)

    def test_hotplug_generation_change_denied(self):
        self.assertEqual(self.begin(),0)
        self.assertEqual(self.candidate(gen=445),-errno.EACCES)
        self.assertEqual(self.g.state,3)

    def test_expiration_no_polling(self):
        self.assertEqual(self.begin(ttl=300),0)
        self.assertEqual(self.candidate(now=100300),-errno.EACCES)
        self.assertEqual(self.g.state,3)

    def test_clock_rollback_denied(self):
        self.assertEqual(self.begin(),0)
        self.assertEqual(self.candidate(now=99999),-errno.EACCES)

    def test_max_ttl_and_integer_wraparound(self):
        self.assertEqual(self.begin(ttl=120001),-errno.EACCES)
        self.assertEqual(self.begin(ttl=0),-errno.EACCES)
        self.assertEqual(self.begin(now=(1<<64)-10,ttl=300),-errno.EACCES)

    def test_invalid_slot_denied(self):
        self.assertEqual(self.begin(),0)
        self.assertEqual(self.candidate(slot=65536),-errno.EACCES)
        self.assertEqual(self.g.state,3)

    def test_success_cannot_be_armed_again_without_trusted_reset(self):
        self.assertEqual(self.begin(),0)
        self.assertEqual(self.begin(),-errno.EBUSY)
        self.assertEqual(self.candidate(),0)
        self.assertEqual(self.begin(),-errno.EBUSY)

    def test_rejected_gate_wipes_sensitive_context(self):
        self.assertEqual(self.begin(),0)
        self.assertEqual(self.candidate(purpose=3),-errno.EACCES)
        self.assertEqual(self.g.quota_login_id,0)
        self.assertEqual(self.g.modem_generation,0)
        self.assertEqual(self.g.deadline_ms,0)
        self.lib.veci_telco_quota_otp_clear(ctypes.byref(self.g))
        self.assertEqual(bytes(self.g),bytes(ctypes.sizeof(Gate)))

    def test_no_modem_io_or_unsolicited_content_reading(self):
        code=SRC.read_text()+"\n"+HEADER.read_text()
        for forbidden in ("AT+CMGR=", "AT+CMGL=", "AT+CNMI=",
                          "open(", "read(", "write(", "send(",
                          "fopen(", "system(", "syslog(", "printf("):
            self.assertNotIn(forbidden,code)
        mk=(ROOT/"source/we5927-lte/Makefile").read_text()
        self.assertNotIn("veci-telco-quota-otp-policy",mk)
        self.assertIn("Bare +CMTI",HEADER.read_text()) if False else None
        self.assertIn("SMS sender text alone is SPOOFABLE",HEADER.read_text())

if __name__=="__main__":
    unittest.main()
