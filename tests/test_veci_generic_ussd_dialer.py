"""Generic VeCI USSD dial code and menu PTY simulation: no real modem calls."""
import json
import os
from pathlib import Path
import pty
import select
import subprocess
import tempfile
import threading
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"source/veci-ussd-dialer/veci-ussd-once.c"

class GenericUSSD(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory()
        cls.binary=Path(cls.temporary.name)/"dialer"
        result=subprocess.run(["gcc","-std=c11","-Os","-Wall","-Wextra","-Werror",
                               "-o",str(cls.binary),str(SRC)],capture_output=True,text=True)
        if result.returncode: raise AssertionError(result.stderr)
    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def dial(self,code,response=b'\r\nOK\r\n\r\n+CUSD: 0,"Service info",15\r\n'):
        master,slave=pty.openpty()
        tty=os.ttyname(slave)
        sent=[]
        def peer():
            raw=b''
            try:
                expire=time.monotonic()+3
                while b'\r' not in raw and time.monotonic()<expire:
                    readable,_,_=select.select([master],[],[],0.1)
                    if readable:
                        try: raw+=os.read(master,512)
                        except OSError: break
                sent.append(raw)
                os.write(master,response)
            except OSError:
                pass
        thread=threading.Thread(target=peer,daemon=True);thread.start()
        try:
            proc=subprocess.run([str(self.binary),tty,code],capture_output=True,text=True,timeout=5)
        finally:
            thread.join(timeout=1);os.close(master);os.close(slave)
        return proc,sent

    def test_generic_dial_codes(self):
        for code in ("*123#","#21#","*808#","*808*7*3*2*1#","##002#","*111*2#"):
            with self.subTest(code=code):
                result,sent=self.dial(code)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertEqual(sent[0],f'AT+CUSD=1,"{code}",15\r'.encode())
                self.assertTrue(json.loads(result.stdout)["ok"])
    def test_manual_menu_choices(self):
        for choice in ("0","1","12","99"):
            result,sent=self.dial(choice,b'\r\nOK\r\n\r\n+CUSD: 1,"Pilih menu",15\r\n')
            self.assertEqual(result.returncode,0,result.stdout)
            self.assertTrue(json.loads(result.stdout)["interactive"])
            self.assertEqual(sent[0],f'AT+CUSD=1,"{choice}",15\r'.encode())
    def test_rejects_non_ussd_or_injection_before_serial_open(self):
        for code in ("", "*", "*#", "#", "*123", "123#", "*123#;AT+CFUN=1",
                     "*123#\rAT+CMGS=1", "ATD123", "12345", "*123 a#", "🤖",
                     "*123"+("1"*35)+"#", "1;2", "001", "*123\"#"):
            with self.subTest(code=code):
                p=subprocess.run([str(self.binary),"/dev/ttyUSB2",code],
                                 capture_output=True,text=True,timeout=2)
                self.assertNotEqual(p.returncode,0)
                self.assertTrue(json.loads(p.stdout).get("ok") is False)
                self.assertNotIn("AT+CUSD=",p.stdout+p.stderr)
    def test_unknown_operator_result_not_fabricated(self):
        r,_=self.dial("*123#",b'\r\nOK\r\n\r\n+CUSD: 0,"31323334",99\r\n')
        self.assertEqual(r.returncode,0)
        o=json.loads(r.stdout)
        self.assertFalse(o["text_supported"])
        self.assertEqual(o["text"],"")
    def test_network_denied(self):
        r,_=self.dial("*123#",b'\r\nERROR\r\n')
        self.assertEqual(json.loads(r.stdout)["reason"],"network_rejected")

if __name__=="__main__": unittest.main()
