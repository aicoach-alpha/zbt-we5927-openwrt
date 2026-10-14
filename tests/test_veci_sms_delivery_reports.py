"""Offline status report decode and privacy test. Never accesses modem."""
import json
import subprocess
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BIN=Path("/tmp/veci-sms-status-report-ci")
def sample(status=0, mr=18, to="261832547698", timestamp="42104121436500"):
    return "0002"+f"{mr:02X}"+"0C91"+to+timestamp+"42104121440000"+f"{status:02X}"

class SmsReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cp=subprocess.run(["gcc","-std=c11","-Os","-Wall","-Wextra","-Werror",
           "-o",str(BIN),str(ROOT/"source/we5927-lte/src/veci-sms-status-report.c")],
            text=True,capture_output=True,timeout=15)
        if cp.returncode:raise AssertionError(cp.stderr)
    @classmethod
    def tearDownClass(cls):BIN.unlink(missing_ok=True)
    def run_decode(self, pdu):
        return subprocess.run([str(BIN)],input=pdu+"\n",text=True,capture_output=True,timeout=3)
    def test_exact_report_statuses(self):
        for code,expect in [(0,"delivered"),(1,"unknown"),(32,"pending"),(64,"failed"),(96,"failed"),(128,"unknown")]:
            with self.subTest(code=code):
                result=self.run_decode(sample(code))
                self.assertEqual(result.returncode,0,result.stderr)
                value=json.loads(result.stdout)
                self.assertEqual(value,{"ok":True,"mr":18,"recipient":"+628123456789","tp_st":code,"state":expect})
                self.assertNotIn(sample(code),result.stdout+result.stderr)
    def test_reject_sms_deliver_and_bad_header(self):
        for raw in [sample().replace("0002","0000",1),sample()[:12],
                    sample().replace("0C91","0C71",1),
                    sample().replace("42104121436500","421A4121436500",1),
                    sample().replace("0C91","FF91",1),
                    sample().lower(),
                    "GG"*25]:
            with self.subTest(pdu=raw[:10]):
                result=self.run_decode(raw)
                self.assertNotEqual(result.returncode,0)
                self.assertEqual(json.loads(result.stdout)["reason"],"invalid_status_report")
                self.assertNotIn(raw,result.stdout+result.stderr)
    def test_readonly_preflight_no_mutations(self):
        s=(ROOT/"scripts/veci-sms-delivery-report-readonly-preflight.sh").read_text()
        for query in ("AT+CMGF?","AT+CSMS?","AT+CNMI?","AT+CNMI=?","AT+CPMS?","AT+CPMS=?"):
            self.assertIn(query,s)
        for forbidden in ("AT+CMGS=","AT+CNMI=0","AT+CNMI=1","AT+CNMI=2","AT+CMGD=","AT+CMGR=","AT+CMGL=",
                          "sysupgrade","/etc/init.d/rpcd restart"):
            self.assertNotIn(forbidden,s)
        result=subprocess.run(["sh","-n",str(ROOT/"scripts/veci-sms-delivery-report-readonly-preflight.sh")],
             capture_output=True,text=True,timeout=3)
        self.assertEqual(result.returncode,0,result.stderr)
if __name__=="__main__":unittest.main()
