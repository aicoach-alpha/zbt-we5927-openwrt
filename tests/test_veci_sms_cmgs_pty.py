"""Native CMGS worker transport tests using a local pseudo-terminal.
No real modem, SMS, credentials, or hardware traffic.
"""
import os
import pty
import select
import subprocess
import threading
import unittest
from pathlib import Path

BIN=Path("/tmp/veci-sms-cmgs-native-ci")
PDU="0001000B912143658709F1000005C82293F904"
class CMGS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(__file__).resolve().parents[1]
        cp=subprocess.run(["gcc","-std=c11","-O2","-Wall","-Wextra","-Werror",
            "-o",str(BIN),str(root/"source/we5927-lte/src/veci-sms-cmgs.c")],
            capture_output=True,text=True,timeout=20)
        if cp.returncode:
            raise AssertionError(cp.stderr)

    @classmethod
    def tearDownClass(cls):
        BIN.unlink(missing_ok=True)

    def run_pty(self,reply="ok"):
        master,slave=pty.openpty()
        path=os.ttyname(slave)
        transcript={"command":b"", "pdu":b""}
        def emulator():
            try:
                buf=b""
                deadline=__import__('time').monotonic()+6
                while b"\r" not in buf and __import__('time').monotonic()<deadline:
                    readable,_,_=select.select([master],[],[],0.2)
                    if readable:buf+=os.read(master,512)
                transcript["command"]=buf
                if reply=="no_prompt":return
                os.write(master,b"\r\n> ")
                buf=b""
                deadline=__import__('time').monotonic()+8
                while b"\x1a" not in buf and __import__('time').monotonic()<deadline:
                    readable,_,_=select.select([master],[],[],0.2)
                    if readable:buf+=os.read(master,512)
                transcript["pdu"]=buf
                if reply=="ok":os.write(master,b"\r\n+CMGS: 18\r\nOK\r\n")
                elif reply=="error":os.write(master,b"\r\n+CMS ERROR: 500\r\n")
                elif reply=="unknown":pass
            except OSError:
                pass
        t=threading.Thread(target=emulator,daemon=True)
        t.start()
        try:
            cp=subprocess.run([str(BIN),path],input=PDU+"\n",
                text=True,capture_output=True,timeout=39)
            t.join(timeout=2)
            return cp,transcript
        finally:
            os.close(master);os.close(slave)

    def test_real_prompt_pdu_ctrlz_and_modem_ack(self):
        p,got=self.run_pty("ok")
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertIn('"status":"accepted_by_modem"',p.stdout)
        self.assertEqual(got["command"],b"AT+CMGS=18\r")
        self.assertEqual(got["pdu"],PDU.encode()+b"\x1a")
        self.assertNotIn(PDU,p.stdout+p.stderr)

    def test_network_rejection_does_not_claim_sent(self):
        p,got=self.run_pty("error")
        self.assertNotEqual(p.returncode,0)
        self.assertIn("network_rejected",p.stdout)
        self.assertEqual(got["pdu"],PDU.encode()+b"\x1a")

    def test_invalid_pdu_cannot_reach_transport(self):
        for bad in ("AT+CMGS=5",PDU[:-2]+"GG",PDU.replace("000100","000110"),""):
            with self.subTest(bad=bad[:4]):
                p=subprocess.run([str(BIN),"/dev/ttyUSB2"],input=bad+"\n",
                    text=True,capture_output=True,timeout=2)
                self.assertNotEqual(p.returncode,0)
                self.assertIn("invalid_submit",p.stdout)
                if bad:
                    self.assertNotIn(bad,p.stdout+p.stderr)

if __name__=="__main__":
    unittest.main()
