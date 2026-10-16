"""Host-only C ABI tests: one authorized SMS slot, one attempt, no content."""
import ctypes
import errno
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"source/we5927-lte/src/veci-sms-read-slot-policy.c"
HEADER=ROOT/"source/we5927-lte/src/veci-sms-read-slot-policy.h"


class Policy(ctypes.Structure):
    _fields_=[
        ("session_binding",ctypes.c_uint64),
        ("request_nonce",ctypes.c_uint64),
        ("modem_generation",ctypes.c_uint64),
        ("slot",ctypes.c_uint),
        ("state",ctypes.c_int),
    ]


class ReadSlotGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.libfile=str(Path(cls.temp.name)/"libveci_sms_read_slot.so")
        r=subprocess.run(
            ["cc","-std=c99","-Wall","-Wextra","-Werror","-O2",
             "-fPIC","-shared",str(SRC),"-o",cls.libfile],
            capture_output=True,text=True,timeout=20)
        if r.returncode:raise AssertionError(r.stderr)
        cls.lib=ctypes.CDLL(cls.libfile)
        cls.lib.veci_sms_read_arm.argtypes=[
            ctypes.POINTER(Policy),ctypes.c_uint,
            ctypes.c_uint64,ctypes.c_uint64,ctypes.c_uint64,
            ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int]
        cls.lib.veci_sms_read_arm.restype=ctypes.c_int
        for name in ("veci_sms_read_issued","veci_sms_read_complete"):
            getattr(cls.lib,name).restype=ctypes.c_int
        cls.lib.veci_sms_read_issued.argtypes=[
            ctypes.POINTER(Policy),ctypes.c_uint,
            ctypes.c_uint64,ctypes.c_uint64,ctypes.c_uint]
        cls.lib.veci_sms_read_complete.argtypes=[
            ctypes.POINTER(Policy),ctypes.c_uint64,
            ctypes.c_uint64,ctypes.c_uint64,ctypes.c_uint,ctypes.c_int]
        # Override issued signature (session binding is uint64).
        cls.lib.veci_sms_read_issued.argtypes=[
            ctypes.POINTER(Policy),ctypes.c_uint64,ctypes.c_uint64,
            ctypes.c_uint64,ctypes.c_uint]
        cls.lib.veci_sms_read_abort.argtypes=[ctypes.POINTER(Policy)]
        cls.lib.veci_sms_read_clear.argtypes=[ctypes.POINTER(Policy)]

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.p=Policy()
        self.slot=4
        self.session=0x123456789ABC
        self.nonce=0xABCDE123456
        self.epoch=0xFFFFFFFF

    def arm(self, flags=(1,1,1,1,1), slot=None,
            session=None,nonce=None,generation=None):
        return self.lib.veci_sms_read_arm(
            ctypes.byref(self.p),self.slot if slot is None else slot,
            self.session if session is None else session,
            self.nonce if nonce is None else nonce,
            self.epoch if generation is None else generation,*flags)

    def issue(self,session=None,nonce=None,generation=None,slot=None):
        return self.lib.veci_sms_read_issued(
            ctypes.byref(self.p),self.session if session is None else session,
            self.nonce if nonce is None else nonce,
            self.epoch if generation is None else generation,
            self.slot if slot is None else slot)

    def complete(self,valid=1,session=None,nonce=None,generation=None,slot=None):
        return self.lib.veci_sms_read_complete(
            ctypes.byref(self.p),self.session if session is None else session,
            self.nonce if nonce is None else nonce,
            self.epoch if generation is None else generation,
            self.slot if slot is None else slot,valid)

    def test_approved_single_slot_one_attempt(self):
        self.assertEqual(self.arm(),0)
        self.assertEqual(self.p.state,1)
        self.assertEqual(self.issue(),0)
        self.assertEqual(self.p.state,2)
        self.assertEqual(self.complete(),0)
        self.assertEqual(self.p.state,3)
        self.assertNotEqual(self.issue(),0)
        self.assertNotEqual(self.arm(),0)
        self.assertNotEqual(self.complete(),0)

    def test_every_approval_gate_independently_required(self):
        for i in range(5):
            flags=[1]*5;flags[i]=0
            with self.subTest(missing=i):
                self.lib.veci_sms_read_clear(ctypes.byref(self.p))
                self.assertEqual(self.arm(tuple(flags)),-errno.EPERM)
                self.assertEqual(self.p.state,0)
                self.assertNotEqual(self.issue(),0)

    def test_unexpected_positive_truthy_flags_rejected(self):
        for i in range(5):
            flags=[1]*5;flags[i]=2
            with self.subTest(flag=i):
                self.lib.veci_sms_read_clear(ctypes.byref(self.p))
                self.assertEqual(self.arm(tuple(flags)),-errno.EPERM)

    def test_slot_range_and_zero_bindings(self):
        for kw in ({"slot":65536},{"slot":2**32-1},
                   {"session":0},{"nonce":0},{"generation":0}):
            with self.subTest(arg=kw):
                self.assertEqual(self.arm(**kw),-errno.EPERM)
                self.assertEqual(self.p.state,0)

    def test_maximum_slot_supported(self):
        self.slot=65535
        self.assertEqual(self.arm(),0)
        self.assertEqual(self.issue(),0)
        self.assertEqual(self.complete(),0)

    def test_reject_other_slot_after_approval_and_poison(self):
        self.assertEqual(self.arm(),0)
        self.assertEqual(self.issue(slot=3),-errno.ESTALE)
        self.assertEqual(self.p.state,4)
        self.assertEqual(self.p.session_binding,0)
        self.assertNotEqual(self.issue(),0)

    def test_reject_session_nonce_or_modem_generation_swap(self):
        for kw in ({"session":55},{"nonce":44},{"generation":2}):
            with self.subTest(mismatch=kw):
                self.lib.veci_sms_read_clear(ctypes.byref(self.p))
                self.assertEqual(self.arm(),0)
                self.assertEqual(self.issue(**kw),-errno.ESTALE)
                self.assertEqual(self.p.state,4)

    def test_invalid_or_truncated_terminal_rejects_and_wipes(self):
        for valid in (0,2,-1):
            with self.subTest(valid=valid):
                self.lib.veci_sms_read_clear(ctypes.byref(self.p))
                self.assertEqual(self.arm(),0)
                self.assertEqual(self.issue(),0)
                self.assertEqual(self.complete(valid=valid),-errno.ESTALE)
                self.assertEqual(self.p.state,4)
                self.assertEqual(self.p.nonce if hasattr(self.p,"nonce") else self.p.request_nonce,0)

    def test_result_from_wrong_session_or_epoch_is_quarantined(self):
        for kw in ({"slot":1},{"session":55},{"nonce":34},{"generation":3}):
            with self.subTest(which=kw):
                self.lib.veci_sms_read_clear(ctypes.byref(self.p))
                self.assertEqual(self.arm(),0)
                self.assertEqual(self.issue(),0)
                self.assertEqual(self.complete(**kw),-errno.ESTALE)
                self.assertEqual(self.p.state,4)

    def test_abort_and_clear_wipe_all(self):
        self.assertEqual(self.arm(),0)
        self.lib.veci_sms_read_abort(ctypes.byref(self.p))
        self.assertEqual(self.p.state,4)
        self.assertEqual(self.p.session_binding,0)
        self.assertEqual(self.p.request_nonce,0)
        self.lib.veci_sms_read_clear(ctypes.byref(self.p))
        self.assertEqual(bytes(self.p),bytes(ctypes.sizeof(Policy)))

    def test_not_linked_to_firmware_and_no_io(self):
        s=SRC.read_text()+"\n"+HEADER.read_text()
        for forbidden in ('we5927-at','AT+CMGR=', 'printf(', 'syslog(',
                          'open(', 'read(', 'write(', 'fopen(', 'send(',
                          'system(', 'fork(', 'sqlite', 'OTPSECRET'):
            self.assertNotIn(forbidden,s)

if __name__=="__main__":
    unittest.main()
