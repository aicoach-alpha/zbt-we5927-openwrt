"""Native CMGS response contract test for staged v1.6.1 send bridge, no modem I/O."""
import json
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
SOURCE=ROOT/"scripts/veci-sms-delivery-v161-staged/veci-sms-send-one"
PDU_SRR="0021000B912143658709F1000005C82293F904"
PDU_LEGACY="0001000B912143658709F1000005C82293F904"

class SendBridge(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.d=pathlib.Path(self.tmp.name)
        d=self.d
        self.path=d/"bin"; self.path.mkdir()
        (d/"feature").write_text("1")
        (d/"board").write_text("zbtlink,zbt-we5927")
        (d/"native_response").write_text('{"ok":true,"status":"accepted_by_modem","mr":18,"report_requested":true}\n')
        usb=d/"devices"/"1-1"
        tty=usb/"1-1:1.4"/"ttyUSB2"
        tty.mkdir(parents=True)
        (usb/"idVendor").write_text("05c6")
        (usb/"idProduct").write_text("902e")
        self.tty=tty
        def script(name,body):
            p=d/name;p.write_text("#!/bin/sh\n"+body);p.chmod(0o700)
            return str(p)
        cmgs=script("cmgs",'''cat > "$FIXTURE_DIR/native_pdu"
cat "$FIXTURE_DIR/native_response"
''')
        at=script("at",'''printf 'AT+CMGF?\r\n+CMGF: 0\r\nOK\r\n'
''')
        jf=self.path/"jsonfilter"
        jf.write_text("""#!/usr/bin/env python3
import json,sys
try:
 args=sys.argv[1:]
 obj=json.loads(args[args.index('-s')+1])
 print(obj[args[args.index('-e')+1].removeprefix('@.')])
except (ValueError,IndexError,KeyError,TypeError):
 sys.exit(1)
""")
        jf.chmod(0o700)
        source=SOURCE.read_text()
        for old,new in [
          ('/usr/libexec/veci-sms-cmgs',cmgs),
          ('/usr/sbin/we5927-at',at),
          ('/etc/veci-sms-feature',str(d/"feature")),
          ('/tmp/sysinfo/board_name',str(d/"board")),
          ('/dev/ttyUSB2',str(d/"fake_tty")),
          ('/sys/class/tty/ttyUSB2/device',str(d/"fake_link")),
          ('/sys/devices/*:1.4/ttyUSB2',str(d/"devices")+'/*:1.4/ttyUSB2'),
          ('/var/lock/we5927-at.lock',str(d/"at.lock")),
          ('[ "$(id -u)" -eq 0 ]','[ 0 -eq 0 ]'),
          ('[ -c '+str(d/"fake_tty")+' ]','[ -f '+str(d/"fake_tty")+' ]')
        ]:
          assert old in source,old
          source=source.replace(old,new)
        (d/"fake_tty").write_text("")
        (d/"fake_link").symlink_to(tty)
        self.worker=d/"send"
        self.worker.write_text(source)
        self.worker.chmod(0o700)
        self.env=os.environ.copy()
        self.env["FIXTURE_DIR"]=str(d)
        self.env["PATH"]=str(self.path)+os.pathsep+self.env.get("PATH","")
    def tearDown(self):
        self.tmp.cleanup()
    def invoke(self,pdu):
        return subprocess.run(["sh",str(self.worker)],input=pdu,text=True,
                              capture_output=True,env=self.env,timeout=4)
    def test_srr_requires_exact_extended_modem_reference(self):
        r=self.invoke(PDU_SRR)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(json.loads(r.stdout),{"ok":True,"status":"accepted_by_modem",
                                               "mr":18,"report_requested":True})
        self.assertEqual((self.d/"native_pdu").read_text(),PDU_SRR+"\n")
    def test_legacy_is_backward_compatible(self):
        (self.d/"native_response").write_text('{"ok":true,"status":"accepted_by_modem"}\n')
        r=self.invoke(PDU_LEGACY)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(json.loads(r.stdout),{"ok":True,"status":"accepted_by_modem"})
    def test_bad_native_or_mismatched_responses_deny_success(self):
        failures=[
         '{"ok":true,"status":"accepted_by_modem"}',
         '{"ok":true,"status":"accepted_by_modem","mr":256,"report_requested":true}',
         '{"ok":true,"status":"accepted_by_modem","mr":18,"report_requested":false}',
         '{"ok":true,"status":"accepted_by_modem","mr":18,"report_requested":true,"recipient":"12345"}',
         '{"ok":true,"status":"accepted_by_modem","mr":18,"report_requested":true,"mr":18}',
        ]
        for response in failures:
            with self.subTest(response=response):
                (self.d/"native_response").write_text(response+"\n")
                r=self.invoke(PDU_SRR)
                self.assertNotEqual(r.returncode,0)
                self.assertEqual(json.loads(r.stdout)["ok"],False)
                self.assertNotIn(PDU_SRR,r.stdout+r.stderr)
    def test_send_disabled_before_serial(self):
        (self.d/"feature").write_text("0")
        r=self.invoke(PDU_SRR)
        self.assertNotEqual(r.returncode,0)
        self.assertFalse((self.d/"native_pdu").exists())

if __name__=="__main__":
    unittest.main()
