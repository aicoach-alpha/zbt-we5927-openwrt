"""Private direct +CDS ingestion integration, offline modem-free tests."""
import json
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
SOURCE=ROOT/"scripts/veci-sms-delivery-v161-staged/veci-sms-report-ingest"
DECODER=ROOT/"source/we5927-lte/src/veci-sms-status-report.c"

def sample(status=0,mr=18):
    return "0002"+f"{mr:02X}"+"0C91261832547698"+"42104121436500"+"42104121440000"+f"{status:02X}"

class ReportIngest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.d=pathlib.Path(self.tmp.name)
        self.d.joinpath("bin").mkdir()
        self.d.joinpath("board").write_text("zbtlink,zbt-we5927")
        self.d.joinpath("feature").write_text("1")
        self.d.joinpath("map_response").write_text('{"ok":true,"matched":true}\n')
        self.decoder=self.d/"decoder"
        cp=subprocess.run(["gcc","-std=c11","-Os","-Wall","-Wextra","-Werror",
                           "-o",str(self.decoder),str(DECODER)],capture_output=True,text=True,timeout=12)
        if cp.returncode:raise AssertionError(cp.stderr)
        mapper=self.d/"map"
        mapper.write_text('''#!/bin/sh
printf '%s,%s,%s,%s\n' "$1" "$2" "$3" "$4" > "$FIXTURE_DIR/applied"
cat "$FIXTURE_DIR/map_response"
''')
        mapper.chmod(0o700)
        filt=self.d/"bin/jsonfilter"
        filt.write_text('''#!/usr/bin/env python3
import json,sys
try:
 a=sys.argv
 value=json.loads(a[a.index("-s")+1])[a[a.index("-e")+1].removeprefix("@.")]
 print(value)
except (ValueError,KeyError,TypeError,IndexError):
 sys.exit(1)
''')
        filt.chmod(0o700)
        code=SOURCE.read_text()
        for old,new in [
            ("DECODER=/usr/libexec/veci-sms-status-report","DECODER="+str(self.decoder)),
            ("MAP=/usr/libexec/veci-sms-delivery-map","MAP="+str(mapper)),
            ("FLAG=/etc/veci-sms-feature","FLAG="+str(self.d/"feature")),
            ("/tmp/sysinfo/board_name",str(self.d/"board")),
            ('[ "$(id -u)" -eq 0 ]','[ 0 -eq 0 ]'),
        ]:
            self.assertIn(old,code)
            code=code.replace(old,new)
        self.worker=self.d/"ingest"
        self.worker.write_text(code);self.worker.chmod(0o700)
        self.env=os.environ.copy()
        self.env["FIXTURE_DIR"]=str(self.d)
        self.env["PATH"]=str(self.d/"bin")+os.pathsep+self.env.get("PATH","")
    def tearDown(self):
        self.tmp.cleanup()
    def ingest(self,pdu,status_length=None):
        n=(len(pdu)//2-1) if status_length is None else status_length
        raw=f"+CDS: {n}\r\n{pdu}\n"
        return subprocess.run(["sh",str(self.worker),"--direct-from-owner"],input=raw,
                              capture_output=True,text=True,timeout=4,env=self.env)
    def test_real_parser_validated_report_then_privileged_apply(self):
        response=self.ingest(sample())
        self.assertEqual(response.returncode,0,response.stdout+response.stderr)
        self.assertEqual(json.loads(response.stdout),{"ok":True,"delivery_recorded":True})
        self.assertEqual((self.d/"applied").read_text().strip(),"--apply,18,+628123456789,0")
        self.assertNotIn("+628123456789",response.stdout+response.stderr)
        self.assertNotIn(sample(),response.stdout+response.stderr)
    def test_failed_and_pending_are_not_delivered(self):
        for st in [32,64,128]:
            with self.subTest(st=st):
                self.d.joinpath("applied").unlink(missing_ok=True)
                response=self.ingest(sample(status=st))
                self.assertEqual(response.returncode,0,response.stdout+response.stderr)
                self.assertEqual((self.d/"applied").read_text().strip().split(",")[-1],str(st))
    def test_bad_urc_never_reaches_map(self):
        for pdu,n in [(sample(),1),("AT+CMGD=1",None),
                      (sample().replace("0002","0000",1),None)]:
            with self.subTest(pdu=pdu[:10]):
                self.d.joinpath("applied").unlink(missing_ok=True)
                result=self.ingest(pdu,n)
                self.assertNotEqual(result.returncode,0)
                self.assertEqual(json.loads(result.stdout)["ok"],False)
                self.assertFalse((self.d/"applied").exists())
    def test_unmatched_report_fails_without_delivered_claim(self):
        self.d.joinpath("map_response").write_text('{"ok":false,"reason":"delivery_unavailable"}\n')
        result=self.ingest(sample())
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(json.loads(result.stdout),{"ok":False,"reason":"report_not_recorded"})
    def test_disabled_sms_never_touches_map(self):
        self.d.joinpath("feature").write_text("0")
        result=self.ingest(sample())
        self.assertNotEqual(result.returncode,0)
        self.assertFalse((self.d/"applied").exists())

if __name__=="__main__":unittest.main()
