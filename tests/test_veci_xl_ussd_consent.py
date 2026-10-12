"""XL *808# inert USSD policy: no operator network calls or AT side effects."""
import ctypes
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"source/we5927-lte/src/veci-xl-ussd-consent.c"
HEADER=ROOT/"source/we5927-lte/src/veci-xl-ussd-consent.h"
IDLE,AWAITING,INTERACTIVE,CLOSED,FAILED=range(5)


class Session(ctypes.Structure):
    _fields_=[("generation",ctypes.c_uint64),
              ("steps",ctypes.c_uint),
              ("state",ctypes.c_int)]


class UsddXLPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir=tempfile.TemporaryDirectory()
        p=Path(cls.dir.name)/"libxl.so"
        x=subprocess.run(["cc","-std=c99","-Wall","-Wextra","-Werror","-O2",
                          "-fPIC","-shared",str(SRC),"-o",str(p)],
                         capture_output=True,text=True)
        if x.returncode:
            raise AssertionError(x.stderr)
        cls.lib=ctypes.CDLL(str(p))
        cls.lib.veci_xl_ussd_begin.argtypes=[
            ctypes.POINTER(Session),ctypes.c_uint64,ctypes.c_int,
            ctypes.c_char_p,ctypes.c_int]
        cls.lib.veci_xl_ussd_begin.restype=ctypes.c_int
        cls.lib.veci_xl_ussd_result.argtypes=[
            ctypes.POINTER(Session),ctypes.c_uint64,ctypes.c_uint]
        cls.lib.veci_xl_ussd_result.restype=ctypes.c_int
        cls.lib.veci_xl_ussd_reply.argtypes=[
            ctypes.POINTER(Session),ctypes.c_uint64,ctypes.c_char_p,
            ctypes.c_int]
        cls.lib.veci_xl_ussd_reply.restype=ctypes.c_int
        cls.lib.veci_xl_ussd_clear.argtypes=[ctypes.POINTER(Session)]

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def setUp(self):
        self.s=Session()

    def begin(self,code=b"*808#",generation=9,xl=1,approved=1):
        return self.lib.veci_xl_ussd_begin(
            ctypes.byref(self.s),generation,xl,code,approved)

    def result(self,mode,gen=9):
        return self.lib.veci_xl_ussd_result(ctypes.byref(self.s),gen,mode)

    def reply(self,choice=b"1",approved=1,gen=9):
        return self.lib.veci_xl_ussd_reply(
            ctypes.byref(self.s),gen,choice,approved)

    def test_correct_start_requires_fresh_user_approval(self):
        self.assertEqual(self.begin(),0)
        self.assertEqual(self.s.state,AWAITING)
        self.assertEqual(self.s.generation,9)
        self.assertEqual(self.s.steps,0)
        self.assertLess(self.begin(),0)

    def test_reject_non_xl_or_no_consent_without_state_change(self):
        for xl,approved in [(0,1),(-1,1),(2,1),(1,0),(1,2),(1,-1)]:
            with self.subTest(xl=xl,approved=approved):
                self.assertLess(self.begin(xl=xl,approved=approved),0)
                self.assertEqual(self.s.state,IDLE)
                self.assertEqual(self.s.generation,0)

    def test_only_current_official_xl_code(self):
        for code in (b"*123#",b"*808*7*1#",b"*808#",b"*808#\rAT",
                     b"*808#\n",b"808",b"",b" *808#",b"**808#"):
            with self.subTest(code=code):
                expected=0 if code==b"*808#" else -1
                rc=self.begin(code=code)
                self.assertEqual(0 if rc==0 else -1,expected)
                self.lib.veci_xl_ussd_clear(ctypes.byref(self.s))

    def test_cannot_start_with_missing_generation_or_code(self):
        self.assertLess(self.begin(generation=0),0)
        self.assertLess(self.begin(code=None),0)
        self.assertEqual(self.s.state,IDLE)

    def test_at_ok_never_completes_ussd_without_urc(self):
        self.assertEqual(self.begin(),0)
        self.assertEqual(self.s.state,AWAITING)
        self.assertLess(self.reply(),0)  # no USSD +CUSD response yet

    def test_dynamic_menu_needs_fresh_one_click_for_every_choice(self):
        self.assertEqual(self.begin(),0)
        self.assertEqual(self.result(1),0)
        self.assertEqual(self.s.state,INTERACTIVE)
        self.assertLess(self.reply(approved=0),0)
        self.assertEqual(self.s.state,INTERACTIVE)
        self.assertEqual(self.reply(b"7"),0)
        self.assertEqual(self.s.state,AWAITING)
        self.assertLess(self.reply(b"1"),0)
        self.assertEqual(self.result(1),0)
        self.assertEqual(self.reply(b"2"),0)
        self.assertEqual(self.s.steps,2)

    def test_numeric_choices_only_and_no_freeform_at(self):
        self.assertEqual(self.begin(),0)
        self.assertEqual(self.result(1),0)
        for choice in (b"",b"01",b"001",b"123",b"*808#",b"1#",
                       b"1;AT",b"1\r",b"yes",b"+1",b" 1",b"1 "):
            with self.subTest(choice=choice):
                self.assertLess(self.reply(choice),0)
                self.assertEqual(self.s.state,INTERACTIVE)
        self.assertEqual(self.reply(b"0"),0)

    def test_network_response_modes_close_or_interactive(self):
        for mode in (0,2,3,4,5):
            with self.subTest(mode=mode):
                self.lib.veci_xl_ussd_clear(ctypes.byref(self.s))
                self.assertEqual(self.begin(),0)
                self.assertEqual(self.result(mode),0)
                self.assertEqual(self.s.state,CLOSED)
                self.assertLess(self.reply(),0)

    def test_bad_ussd_mode_poisons(self):
        self.assertEqual(self.begin(),0)
        self.assertLess(self.result(6),0)
        self.assertEqual(self.s.state,FAILED)
        self.assertLess(self.result(1),0)

    def test_wrong_epoch_denies_response_and_choice(self):
        self.assertEqual(self.begin(),0)
        self.assertLess(self.result(1,gen=8),0)
        self.assertEqual(self.s.state,AWAITING)
        self.assertEqual(self.result(1),0)
        self.assertLess(self.reply(gen=8),0)
        self.assertEqual(self.s.state,INTERACTIVE)

    def test_no_auto_replies_and_six_step_cap(self):
        self.assertEqual(self.begin(),0)
        for idx in range(6):
            self.assertEqual(self.result(1),0)
            self.assertEqual(self.reply(str(idx).encode()),0)
        self.assertEqual(self.s.steps,6)
        self.assertEqual(self.result(1),0)
        self.assertLess(self.reply(b"1"),0)
        self.assertEqual(self.s.state,FAILED)

    def test_cancel_zeroizes_generation_and_requires_new_consent(self):
        self.assertEqual(self.begin(),0)
        self.assertEqual(self.result(1),0)
        self.lib.veci_xl_ussd_clear(ctypes.byref(self.s))
        self.assertEqual(self.s.state,IDLE)
        self.assertEqual(self.s.generation,0)
        self.assertEqual(self.s.steps,0)
        self.assertLess(self.reply(b"1"),0)
        self.assertEqual(self.begin(generation=10),0)

    def test_source_has_no_modem_or_network_access(self):
        src=SRC.read_text()
        mk=(ROOT/"source/we5927-lte/Makefile").read_text()
        self.assertNotIn("veci-xl-ussd-consent.c",mk)
        for forbidden in ("/dev/", "we5927-at", "AT+CUSD=", "open(",
                          "printf(", "socket(", "syslog(", "system(", "popen("):
            self.assertNotIn(forbidden,src)
        self.assertIn("one_time_approval != 1",src)
        self.assertIn("fresh_approval != 1",src)
        self.assertIn('strcmp(dial, "*808#")',src)


if __name__=="__main__":
    unittest.main()
