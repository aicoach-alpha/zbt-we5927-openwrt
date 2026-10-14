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

    @staticmethod
    def multipart_pdu(text="HELLO", unicode=False, reference=25, total=2, part=1):
        udh=bytes([5,0,3,reference,total,part])
        if unicode:
            data=udh+text.encode("utf-16-be")
            udl=len(data)
            dcs=8
        else:
            septets=[ord(char) for char in text]
            assert all(0<z<128 for z in septets)
            udl=7+len(septets)
            data=bytearray((udl*7+7)//8)
            data[:6]=udh
            for i,val in enumerate(septets):
                for bit in range(7):
                    if val & (1<<bit):
                        offset=(7+i)*7+bit
                        data[offset//8] |= 1<<(offset%8)
            dcs=0
        header=bytes([0,0x41,0,11,0x91])+bytes.fromhex("2143658709F1")
        return (header+bytes([0,dcs,udl])+data).hex().upper()

    def run_pty(self,reply="ok",pdu=PDU):
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
            cp=subprocess.run([str(BIN),path],input=pdu+"\n",
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

    def test_multipart_gsm7_concat_header_accepted(self):
        pdu=self.multipart_pdu("HELLO",reference=25,total=2,part=1)
        p,got=self.run_pty("ok",pdu)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertIn('accepted_by_modem',p.stdout)
        self.assertEqual(got["command"],f"AT+CMGS={len(pdu)//2-1}".encode()+bytes([13]))
        self.assertEqual(got["pdu"],pdu.encode()+bytes([26]))
        self.assertNotIn(pdu,p.stdout+p.stderr)

    def test_multipart_ucs2_concat_header_accepted(self):
        pdu=self.multipart_pdu("你好",unicode=True,reference=59,total=3,part=2)
        p,got=self.run_pty("ok",pdu)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertIn('accepted_by_modem',p.stdout)
        self.assertEqual(got["pdu"],pdu.encode()+bytes([26]))

    def test_reject_malformed_concat_without_modem_commands(self):
        for pdu in [
            self.multipart_pdu("HELLO",total=1),
            self.multipart_pdu("HELLO",part=3),
            self.multipart_pdu("HELLO",unicode=False)[:-2],
            self.multipart_pdu("你好",unicode=True)[:-2],
            self.multipart_pdu("HELLO").replace("05000319","06000319"),
        ]:
            with self.subTest(pdu=pdu[:22]):
                p=subprocess.run([str(BIN),"/dev/ttyUSB2"],input=pdu+chr(10),
                    text=True,capture_output=True,timeout=2)
                self.assertNotEqual(p.returncode,0)
                self.assertIn("invalid_submit",p.stdout)

    def test_status_report_requested_returns_tp_mr(self):
        # TP-SRR=1 changes SMS-SUBMIT first octet 01->21.
        pdu=PDU.replace("000100","002100",1)
        p,got=self.run_pty("ok",pdu)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        import json
        self.assertEqual(json.loads(p.stdout),{
            "ok":True,"status":"accepted_by_modem",
            "mr":18,"report_requested":True})
        self.assertEqual(got["pdu"],pdu.encode()+bytes([26]))
        self.assertNotIn(pdu,p.stdout+p.stderr)

    def test_multipart_status_report_requested_returns_tp_mr(self):
        pdu=self.multipart_pdu("HELLO",total=2,part=1)
        pdu=pdu[:2]+"61"+pdu[4:]
        p,got=self.run_pty("ok",pdu)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        import json
        self.assertEqual(json.loads(p.stdout)["mr"],18)
        self.assertTrue(json.loads(p.stdout)["report_requested"])
        self.assertEqual(got["pdu"],pdu.encode()+bytes([26]))

    def test_invalid_submit_first_octet_must_not_send(self):
        invalid=PDU[:2]+"A1"+PDU[4:]
        p=subprocess.run([str(BIN),"/dev/ttyUSB2"],input=invalid+chr(10),
                         text=True,capture_output=True,timeout=3)
        self.assertIn("invalid_submit",p.stdout)
        self.assertNotEqual(p.returncode,0)

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
