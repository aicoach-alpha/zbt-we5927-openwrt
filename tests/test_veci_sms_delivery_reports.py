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
    def run_decode(self, pdu, *args):
        return subprocess.run([str(BIN),*args],input=pdu+"\n",text=True,capture_output=True,timeout=3)
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
    def test_direct_cds_urc_correlates_only_valid_tpdu_length(self):
        pdu=sample(status=0,mr=18)
        direct=self.run_decode("+CDS: "+str(len(pdu)//2-1)+"\r\n"+pdu,"--direct-urc")
        self.assertEqual(direct.returncode,0,direct.stdout+direct.stderr)
        data=json.loads(direct.stdout)
        self.assertEqual(data,{"ok":True,"route":"direct_urc","mr":18,
                               "recipient":"+628123456789","tp_st":0,"state":"delivered"})
        self.assertNotIn(pdu,direct.stdout+direct.stderr)
        for invalid in ["+CDS: 1\r\n"+pdu,
                        "+CDS: 999\r\n"+pdu,
                        "+CDS: -1\r\n"+pdu,
                        "+CMGL: 24\r\n"+pdu,
                        "+CDS: 24;AT+CMGD=1\r\n"+pdu]:
            with self.subTest(header=invalid[:24]):
                res=self.run_decode(invalid,"--direct-urc")
                self.assertNotEqual(res.returncode,0)
                self.assertEqual(json.loads(res.stdout)["reason"],"invalid_status_report")

    def test_stored_cdsi_urc_index_only_and_strict_storage(self):
        for route,expect in [('+CDSI: "ME",3',{"ok":True,"route":"stored_indication",
                                                "storage":"ME","index":3}),
                             ('+CDSI: "SM",255',{"ok":True,"route":"stored_indication",
                                                "storage":"SM","index":255})]:
            res=self.run_decode(route,"--stored-urc")
            self.assertEqual(res.returncode,0,res.stdout+res.stderr)
            self.assertEqual(json.loads(res.stdout),expect)
        for invalid in ['+CDSI: "MT",3','+CDSI: "ME",-1','+CDSI: "ME",65536',
                        '+CDSI: "ME",3;AT+CMGD=1','+CDSI: "ME",',
                        '+CDS: 12','+CDSI: "SM",abc']:
            with self.subTest(invalid=invalid):
                res=self.run_decode(invalid,"--stored-urc")
                self.assertNotEqual(res.returncode,0)
                self.assertEqual(json.loads(res.stdout)["ok"],False)

    def test_cnmi_and_cpms_test_only_preflight(self):
        source=(ROOT/"scripts/veci-sms-delivery-routing-capability-v161.sh").read_text()
        self.assertIn("AT+CNMI=?",source)
        self.assertIn("AT+CPMS=?",source)
        self.assertNotIn("AT+CNMI=2,",source)
        self.assertNotIn("AT+CNMI=1,",source)
        for dangerous in ("AT+CMGS=","AT+CMGD=","AT+CMGR=","AT+CMGL=",
                          "/etc/init.d/rpcd restart","sysupgrade"):
            self.assertNotIn(dangerous,source)
        cp=subprocess.run(["sh","-n",str(ROOT/"scripts/veci-sms-delivery-routing-capability-v161.sh")],
            capture_output=True,text=True,timeout=3)
        self.assertEqual(cp.returncode,0,cp.stderr)
        self.assertIn("STATUS_REPORT_STORED_INDICATION_SUPPORTED=",source)
        self.assertIn("ROUTING_CONFIGURATION_CHANGED=false",source)

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
