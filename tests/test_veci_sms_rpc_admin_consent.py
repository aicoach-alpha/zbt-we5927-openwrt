"""Isolated rpcd entrypoint / ACL tests; no actual modem or SMS accessed."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/"source/veci-sms-inbox-we5927"
RPC=PACKAGE/"files/usr/libexec/rpcd/veci.sms"
WORKER=PACKAGE/"files/usr/libexec/veci-sms-inbox-index"
ACL=PACKAGE/"files/usr/share/rpcd/acl.d/veci-sms-inbox-we5927.json"


class SmsRpcConsent(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.bin=self.root/"bin"
        self.bin.mkdir()
        self.count=self.root/"calls"
        self.dummy=self.root/"mock-worker"
        self.dummy.write_text(
            "#!/bin/sh\n"
            "printf x >> '"+str(self.count)+"'\n"
            'echo \'{"ok":true,"source":"on_demand_cmgl","side_effect_acknowledged":true,"count":1,"messages":[{"index":0,"status":0,"tpdu_octets":163}]}\'\n'
        )
        self.dummy.chmod(0o700)
        mock=self.bin/"jsonfilter"
        mock.write_text(
            "#!/usr/bin/env python3\n"
            "import sys,json\n"
            "try:\n"
            " a=sys.argv; d=json.loads(a[a.index('-s')+1]); k=a[a.index('-e')+1].split('.')[-1]\n"
            " v=d[k]; assert isinstance(v,str); print(v)\n"
            "except (ValueError,KeyError,IndexError,AssertionError,TypeError): sys.exit(2)\n"
        )
        mock.chmod(0o700)
        fake_id=self.bin/"id"
        fake_id.write_text("#!/bin/sh\n[ \"$1\" = '-u' ] && echo 0\n")
        fake_id.chmod(0o700)
        self.test_script=self.root/"veci.sms"
        text=RPC.read_text().replace("WORKER=/usr/libexec/veci-sms-inbox-index",
                                     "WORKER="+str(self.dummy))
        self.test_script.write_text(text)
        self.env={**os.environ, "PATH":str(self.bin)+":"+os.environ["PATH"]}

    def call(self, payload=None, method="listIndex"):
        return subprocess.run(["sh",str(self.test_script),"call",method],
                              input=json.dumps(payload) if not isinstance(payload,str) else payload,
                              text=True,capture_output=True,timeout=4,env=self.env)

    def test_shell_syntax_and_worker_still_identical_to_hardware_uat(self):
        for f in (RPC, WORKER):
            p=subprocess.run(["sh","-n",str(f)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
        old=(ROOT/"scripts/veci-sms-inbox-index-preview.sh").read_bytes()
        self.assertEqual(WORKER.read_bytes(),old)

    def test_method_ubus_signature_is_single_fixed_write_action(self):
        p=subprocess.run(["sh",str(self.test_script),"list"],text=True,capture_output=True,env=self.env)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(json.loads(p.stdout),{"listIndex":{"scope":"str","ack_unread_status":"str"}})
        acl=json.loads(ACL.read_text())["veci-sms-inbox-we5927"]
        self.assertEqual(acl["read"]["ubus"],{})
        self.assertEqual(acl["write"]["ubus"],{"veci.sms":["listIndex"]})
        self.assertNotIn("veci.cellular",str(acl))
        self.assertNotIn("sendSms",str(acl))
        self.assertNotIn("readSms",str(acl))

    def test_missing_consent_never_calls_modem_worker(self):
        requests=[
            {}, {"scope":"metadata_only"}, {"ack_unread_status":"I_ACCEPT_UNREAD_TO_READ"},
            {"scope":"all", "ack_unread_status":"I_ACCEPT_UNREAD_TO_READ"},
            {"scope":"metadata_only","ack_unread_status":"true"},
            {"scope":"metadata_only","ack_unread_status":True},
            {"scope":"metadata_only","ack_unread_status":"I_ACCEPT_UNREAD_TO_READ "},
            "not json", json.dumps({"scope":"metadata_only","ack_unread_status":"I_ACCEPT_UNREAD_TO_READ"})+" "*600,
        ]
        for payload in requests:
            with self.subTest(payload=str(payload)[:60]):
                p=self.call(payload)
                self.assertEqual(p.returncode,0,p.stderr)
                self.assertFalse(json.loads(p.stdout)["ok"])
                self.assertFalse(self.count.exists())

    def test_one_consented_request_only_calls_fixed_helper_once(self):
        p=self.call({"scope":"metadata_only","ack_unread_status":"I_ACCEPT_UNREAD_TO_READ"})
        self.assertEqual(p.returncode,0,p.stderr)
        x=json.loads(p.stdout)
        self.assertTrue(x["ok"])
        self.assertEqual(x["messages"],[{"index":0,"status":0,"tpdu_octets":163}])
        self.assertEqual(self.count.read_text(),"x")
        self.assertNotIn("OTP",p.stdout)

    def test_cannot_call_arbitrary_method(self):
        p=self.call({"scope":"metadata_only","ack_unread_status":"I_ACCEPT_UNREAD_TO_READ"},"AT+CMGS")
        self.assertFalse(json.loads(p.stdout)["ok"])
        self.assertFalse(self.count.exists())

    def test_worker_secret_output_rejected_as_whole(self):
        self.dummy.write_text("#!/bin/sh\nprintf '%s\\n' 'OTPSECRET' \n")
        p=self.call({"scope":"metadata_only","ack_unread_status":"I_ACCEPT_UNREAD_TO_READ"})
        self.assertFalse(json.loads(p.stdout)["ok"])
        self.assertNotIn("OTPSECRET",p.stdout)

    def test_invalid_metadata_shape_is_denied(self):
        bad=[
            '{"ok":true,"source":"on_demand_cmgl","side_effect_acknowledged":true,"count":1,"messages":[{"index":0,"status":0,"tpdu_octets":163,"body":"123456"}]}',
            '{"ok":true,"source":"on_demand_cmgl","side_effect_acknowledged":true,"count":1,"messages":[{"index":0,"status":0,"tpdu_octets":163}]}OTP',
            '{"ok":true,"source":"on_demand_cmgl","side_effect_acknowledged":true,"count":17,"messages":[]}',
            '{"ok":true,"source":"on_demand_cmgl","side_effect_acknowledged":true,"count":1,"messages":[{"index":0,"status":9,"tpdu_octets":163}]}'
        ]
        for v in bad:
            self.dummy.write_text("#!/bin/sh\nprintf '%s\\n' '"+v+"'\n")
            with self.subTest(first=v[:50]):
                p=self.call({"scope":"metadata_only","ack_unread_status":"I_ACCEPT_UNREAD_TO_READ"})
                self.assertFalse(json.loads(p.stdout)["ok"])
                self.assertNotIn("body",p.stdout)

    def test_package_opt_in_and_no_modem_restart(self):
        mk=(PACKAGE/"Makefile").read_text()
        self.assertIn("PKG_NAME:=veci-sms-inbox-we5927",mk)
        self.assertIn("veci.sms",mk)
        self.assertNotIn("/etc/init.d/rpcd restart",mk)
        self.assertNotIn("sysupgrade",mk)
        self.assertNotIn("python3",mk)
        src=RPC.read_text()
        self.assertNotIn("logger",src)
        self.assertNotIn("AT+CMGL=4'",src)
        self.assertNotIn("echo \"$input\"",src)
        self.assertIn("head -c 513",src)

if __name__=="__main__":
    unittest.main()
