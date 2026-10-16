"""Offline source-only SMS read one-use capability tests: no modem, no browser."""
import ctypes
import errno
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"source/we5927-lte/src/veci-sms-read-capability.c"
HD=ROOT/"source/we5927-lte/src/veci-sms-read-capability.h"
MAX64=(1<<64)-1

class Cap(ctypes.Structure):
    _fields_=[
        ("trusted_session",ctypes.c_ubyte*16),
        ("nonce",ctypes.c_ubyte*16),
        ("generation",ctypes.c_uint64),
        ("armed_ms",ctypes.c_uint64),
        ("expires_ms",ctypes.c_uint64),
        ("slot",ctypes.c_uint32),
        ("state",ctypes.c_uint32)
    ]

SESSION=(ctypes.c_ubyte*16)(*range(1,17))
NONCE=(ctypes.c_ubyte*16)(*range(101,117))
OTHER=(ctypes.c_ubyte*16)(*range(17,33))
ZERO=(ctypes.c_ubyte*16)()

class CapabilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.so=str(Path(cls.tmp.name)/"libveci-capability.so")
        r=subprocess.run(["cc","-std=c99","-Wall","-Wextra","-Werror","-O2",
                          "-shared","-fPIC",str(SRC),"-o",cls.so],
                         text=True,capture_output=True,timeout=15)
        if r.returncode:raise AssertionError(r.stderr)
        cls.lib=ctypes.CDLL(cls.so)
        cls.lib.veci_sms_cap_arm.argtypes=[
          ctypes.POINTER(Cap),ctypes.POINTER(ctypes.c_ubyte),
          ctypes.POINTER(ctypes.c_ubyte),ctypes.c_uint,
          ctypes.c_uint64,ctypes.c_uint64,ctypes.c_uint,
          ctypes.c_int,ctypes.c_int,ctypes.c_int]
        cls.lib.veci_sms_cap_arm.restype=ctypes.c_int
        cls.lib.veci_sms_cap_consume.argtypes=[
          ctypes.POINTER(Cap),ctypes.POINTER(ctypes.c_ubyte),
          ctypes.POINTER(ctypes.c_ubyte),ctypes.c_uint,
          ctypes.c_uint64,ctypes.c_uint64]
        cls.lib.veci_sms_cap_consume.restype=ctypes.c_int
        cls.lib.veci_sms_cap_clear.argtypes=[ctypes.POINTER(Cap)]

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def setUp(self):
        self.c=Cap()
        self.slot=4
        self.generation=9292
        self.now=100_000

    def arm(self,s=SESSION,n=NONCE,slot=None,gen=None,now=None,
            ttl=15_000,flags=(1,1,1)):
        return self.lib.veci_sms_cap_arm(
          ctypes.byref(self.c),s,n,
          self.slot if slot is None else slot,
          self.generation if gen is None else gen,
          self.now if now is None else now,
          ttl,*flags)

    def use(self,s=SESSION,n=NONCE,slot=None,gen=None,now=None):
        return self.lib.veci_sms_cap_consume(
          ctypes.byref(self.c),s,n,
          self.slot if slot is None else slot,
          self.generation if gen is None else gen,
          self.now+100 if now is None else now)

    def test_happy_path_consumed_exactly_once(self):
        self.assertEqual(self.arm(),0)
        self.assertEqual(self.c.state,1)
        self.assertEqual(self.use(),0)
        self.assertEqual(self.c.state,2)
        self.assertEqual(self.use(),-errno.EACCES)
        self.assertEqual(bytes(self.c.nonce),bytes(16))
        self.assertEqual(bytes(self.c.trusted_session),bytes(16))

    def test_failed_session_comparison_consumes_token(self):
        self.assertEqual(self.arm(),0)
        self.assertEqual(self.use(s=OTHER),-errno.EACCES)
        self.assertEqual(self.use(),-errno.EACCES)
        self.assertEqual(self.c.state,2)

    def test_failed_random_token_comparison_consumes_token(self):
        self.assertEqual(self.arm(),0)
        self.assertEqual(self.use(n=OTHER),-errno.EACCES)
        self.assertEqual(self.use(),-errno.EACCES)
        self.assertEqual(self.c.state,2)

    def test_wrong_slot_or_generation_consumes_token(self):
        for kwargs in ({"slot":2},{"slot":65536},{"gen":9293}):
            with self.subTest(kwargs=kwargs):
                self.lib.veci_sms_cap_clear(ctypes.byref(self.c))
                self.assertEqual(self.arm(),0)
                self.assertEqual(self.use(**kwargs),-errno.EACCES)
                self.assertEqual(self.use(),-errno.EACCES)

    def test_clock_rollback_fails_closed(self):
        self.assertEqual(self.arm(),0)
        self.assertEqual(self.use(now=self.now-1),-errno.EACCES)
        self.assertEqual(self.use(),-errno.EACCES)

    def test_expiry_exact_boundary_and_before(self):
        self.assertEqual(self.arm(ttl=3000),0)
        self.assertEqual(self.use(now=self.now+2999),0)
        self.lib.veci_sms_cap_clear(ctypes.byref(self.c))
        self.assertEqual(self.arm(ttl=3000),0)
        self.assertEqual(self.use(now=self.now+3000),-errno.EACCES)

    def test_invalid_ttl_rejected(self):
        for ttl in (0,30001,0xFFFFFFFF):
            with self.subTest(ttl=ttl):
                self.assertEqual(self.arm(ttl=ttl),-errno.EACCES)
                self.assertEqual(self.c.state,0)

    def test_overflow_rejected(self):
        self.assertEqual(self.arm(now=MAX64-2,ttl=100),-errno.EACCES)
        self.assertEqual(self.c.state,0)

    def test_all_security_proofs_are_required_exactly_one(self):
        for i in range(3):
            for bad in (0,2,-1):
                with self.subTest(i=i,bad=bad):
                    vals=[1,1,1]
                    vals[i]=bad
                    self.assertEqual(self.arm(flags=tuple(vals)),-errno.EACCES)
                    self.assertEqual(self.c.state,0)

    def test_zero_bindings_zero_epoch_and_invalid_slot(self):
        for kwargs in ({"s":ZERO},{"n":ZERO},{"gen":0},{"slot":65536},{"now":0}):
            with self.subTest(kwargs=repr(kwargs)):
                self.assertEqual(self.arm(**kwargs),-errno.EACCES)
                self.assertEqual(self.c.state,0)

    def test_rearm_without_explicit_server_reset_denied(self):
        self.assertEqual(self.arm(),0)
        self.assertEqual(self.arm(),-errno.EBUSY)
        self.assertEqual(self.use(),0)
        self.assertEqual(self.arm(),-errno.EBUSY)
        self.lib.veci_sms_cap_clear(ctypes.byref(self.c))
        self.assertEqual(self.arm(n=OTHER),0)

    def test_source_is_inert_without_credentials_or_sms(self):
        s=SRC.read_text()+HD.read_text()
        for prohibited in ("AT+CMGR=", "/dev/ttyUSB", "ubus call",
                           "syslog(", "printf(", "fprintf(", "open(",
                           "write(", "read(", "send(", "system("):
            self.assertNotIn(prohibited,s)
        firmware=(ROOT/"source/we5927-lte/Makefile").read_text()
        self.assertNotIn("veci-sms-read-capability",firmware)
        self.assertIn("SERVER-VERIFIED",HD.read_text())
        self.assertIn("under a process lock",HD.read_text())

if __name__=="__main__":
    unittest.main()
