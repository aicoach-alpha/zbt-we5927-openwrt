"""Draft SMS storage regression in an isolated temp directory; never touches modem or router."""
import json
import os
import pathlib
import subprocess
import tempfile
import unittest
SRC=pathlib.Path(__file__).resolve().parents[1]/"scripts/veci-sms-mifi-v157-staged/veci-sms-drafts"
PDU="0001000B912143658709F1000005C82293F904"
SECOND="0001000B912143658709F1000003C14021"

class Drafts(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        root=pathlib.Path(self.tmp.name)
        (root/"board").write_text("zbtlink,zbt-we5927")
        (root/"flag").write_text("1")
        (root/"drafts").write_text("")
        code=SRC.read_text().replace("/tmp/sysinfo/board_name",str(root/"board"))
        code=code.replace("/etc/veci-sms-feature",str(root/"flag"))
        code=code.replace("/etc/veci-sms-drafts",str(root/"drafts"))
        code=code.replace('[ "$(id -u)" = 0 ]','[ 0 = 0 ]')
        self.exe=root/"drafts-worker"
        self.exe.write_text(code)
        self.exe.chmod(0o700)
        self.root=root

    def tearDown(self):
        self.tmp.cleanup()

    def cmd(self,*args,stdin=""):
        return subprocess.run(["sh",str(self.exe),*args],input=stdin,text=True,
            capture_output=True,timeout=3)

    def test_add_edit_list_delete_and_stale_rejection(self):
        first=self.cmd("--save","0","-",stdin=PDU)
        self.assertEqual(first.returncode,0,first.stdout+first.stderr)
        self.assertEqual(json.loads(first.stdout)["id"],1)
        saved=self.cmd("--list")
        self.assertEqual(saved.returncode,0)
        history=json.loads(saved.stdout)
        self.assertEqual(history["count"],1)
        self.assertEqual(history["drafts"][0]["pdu"],PDU)
        changed=self.cmd("--save","1",PDU,stdin=SECOND)
        self.assertEqual(changed.returncode,0,changed.stdout)
        self.assertNotEqual(self.cmd("--save","1",PDU,stdin=PDU).returncode,0)
        self.assertNotEqual(self.cmd("--delete","1",PDU).returncode,0)
        deleted=self.cmd("--delete","1",SECOND)
        self.assertEqual(deleted.returncode,0,deleted.stdout)
        self.assertEqual(json.loads(self.cmd("--list").stdout)["count"],0)

    def test_maximum_ten_and_disabled_switch(self):
        for i in range(10):
            self.assertEqual(self.cmd("--save","0","-",stdin=PDU).returncode,0)
        self.assertNotEqual(self.cmd("--save","0","-",stdin=PDU).returncode,0)
        self.assertEqual(json.loads(self.cmd("--list").stdout)["count"],10)
        (self.root/"flag").write_text("0")
        self.assertNotEqual(self.cmd("--list").returncode,0)
        self.assertNotEqual(self.cmd("--delete","1",PDU).returncode,0)
        self.assertEqual(json.loads((self.root/"drafts").read_text().splitlines()[0].split("|")[0]),1)

    def test_bounded_inputs_and_non_disclosure(self):
        bad=self.cmd("--save","0","-",stdin="HELLO WORLD")
        self.assertNotEqual(bad.returncode,0)
        self.assertNotIn("HELLO WORLD",bad.stdout+bad.stderr)
        self.assertNotEqual(self.cmd("--save","11","-",stdin=PDU).returncode,0)
        self.assertNotEqual(self.cmd("--save","0","-",stdin=PDU+"A").returncode,0)
        self.assertEqual((self.root/"drafts").read_text(),"")

if __name__=="__main__":
    unittest.main()
