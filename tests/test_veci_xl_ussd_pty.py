"""XL on-demand USSD with delayed asynchronous +CUSD, simulated PTY only."""
import json
import os
import pathlib
import pty
import select
import subprocess
import tempfile
import threading
import time
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
SRC=ROOT/"source/we5927-lte/src/veci-xl-ussd-once.c"

class XLUSSD(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.bin=pathlib.Path(cls.tmp.name)/"veci-xl-ussd-once"
        cp=subprocess.run(["gcc","-std=c11","-Os","-Wall","-Wextra","-Werror",
                           "-o",str(cls.bin),str(SRC)],text=True,capture_output=True)
        if cp.returncode:raise AssertionError(cp.stderr)
    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
    def simulate(self,code="*808#",frames=None):
        master,slave=pty.openpty()
        path=os.ttyname(slave)
        received=[]
        errors=[]
        def modem():
            try:
                sofar=b""
                limit=time.monotonic()+4
                while b"\r" not in sofar and time.monotonic()<limit:
                    ready,_,_=select.select([master],[],[],0.1)
                    if ready:
                        try: sofar+=os.read(master,512)
                        except OSError:break
                received.append(sofar)
                for payload in frames or [b'\r\nAT+CUSD=1,"*808#",15\r\n\r\nOK\r\n',
                                          b'\r\n+CUSD: 1,"1. Cek kuota, 2. Info",15\r\n']:
                    time.sleep(0.02)
                    os.write(master,payload)
            except Exception as exc:
                errors.append(str(exc))
        th=threading.Thread(target=modem,daemon=True)
        th.start()
        try:
            cp=subprocess.run([str(self.bin),path,code],text=True,
                              capture_output=True,timeout=5)
        finally:
            th.join(timeout=1)
            os.close(master);os.close(slave)
        return cp,received,errors
    def test_response_after_ok_is_not_missed(self):
        cp,sent,errors=self.simulate()
        self.assertFalse(errors)
        self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
        self.assertEqual(sent[0],b'AT+CUSD=1,"*808#",15\r')
        d=json.loads(cp.stdout)
        self.assertTrue(d["ok"])
        self.assertTrue(d["interactive"])
        self.assertTrue(d["text_supported"])
        self.assertEqual(d["text"],"1. Cek kuota, 2. Info")
    def test_urc_before_ok(self):
        cp,_,_=self.simulate(frames=[
            b'\r\n+CUSD: 0,"Sisa kuota 2 GB",15\r\n',
            b'\r\nOK\r\n'
        ])
        self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
        d=json.loads(cp.stdout)
        self.assertEqual(d["text"],"Sisa kuota 2 GB")
        self.assertFalse(d["interactive"])
    def test_ucs2(self):
        cp,_,_=self.simulate(frames=[b'\r\nOK\r\n',
            b'\r\n+CUSD: 0,"00480061006C006F",72\r\n'])
        self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
        self.assertEqual(json.loads(cp.stdout)["text"],"Halo")
    def test_unknown_dcs_does_not_fabricate_text(self):
        cp,_,_=self.simulate(frames=[
           b'\r\nOK\r\n', b'\r\n+CUSD: 0,"4A687473",99\r\n'])
        self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
        d=json.loads(cp.stdout)
        self.assertFalse(d["text_supported"])
        self.assertEqual(d["text"],"")
    def test_response_injection_fails_without_echoing(self):
        cp,_,_=self.simulate(frames=[b'\r\nOK\r\n',
            b'\r\n+CUSD: 0,"malicious\x01payload",15\r\n'])
        self.assertNotEqual(cp.returncode,0)
        self.assertFalse(json.loads(cp.stdout)["ok"])
        self.assertNotIn("malicious",cp.stdout+cp.stderr)
    def test_allowed_menu_choice_does_not_auto_follow(self):
        cp,sent,_=self.simulate("2",frames=[b'\r\nOK\r\n',
             b'\r\n+CUSD: 0,"Paket anda",15\r\n'])
        self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
        self.assertEqual(sent[0],b'AT+CUSD=1,"2",15\r')
    def test_invalid_dial_fails_before_opening_serial(self):
        for code in ("*123#","*808*99#", "AT+CMGD=1","1;2","-1", "000",""):
            cp=subprocess.run([str(self.bin),"/dev/ttyUSB2",code],
                              capture_output=True,text=True,timeout=2)
            self.assertNotEqual(cp.returncode,0)
            self.assertNotIn("AT+",cp.stdout)
    def test_unsolicited_network_error_is_not_success(self):
        cp,_,_=self.simulate(frames=[b'\r\nERROR\r\n'])
        self.assertNotEqual(cp.returncode,0)
        self.assertEqual(json.loads(cp.stdout)["reason"],"network_rejected")

if __name__=="__main__":unittest.main()
