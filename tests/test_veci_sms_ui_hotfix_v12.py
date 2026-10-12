"""Run v1.2 exact-device hotfix in isolated fake OpenWrt filesystem."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
INSTALLER=ROOT/"scripts/veci-sms-storage-ui-exact-live-hotfix-v12.sh"
PATCH=ROOT/"scripts/veci-sms-ui-live-captured-20261012/cellular.js"
ORIGINAL_SHA="0a4e78d5368806b31441612b8979ab7b2ac8f425890cfd89104f969accd8ee18"
PATCHED_SHA="2deb013e6ccf433b9c3abc3d7f02aafb33739dd1b5b5f222d4de501865314d40"

class SafeHotfix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patch=PATCH.read_bytes()
        assert hashlib.sha256(cls.patch).hexdigest()==PATCHED_SHA

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.page=self.root/"www/js/pages/cellular.js"
        self.page.parent.mkdir(parents=True)
        self.backup=self.root/"backups/ui-v12"
        self.board=self.root/"sysinfo/board_name"
        self.board.parent.mkdir(parents=True)
        self.board.write_text("zbtlink,zbt-we5927\n")
        self.bin=self.root/"bin"
        self.bin.mkdir()
        self.output=self.root/"installer.sh"
        script=INSTALLER.read_text()
        script=script.replace("FILE=/www/veci/js/pages/cellular.js",
                              "FILE="+str(self.page))
        script=script.replace("BACKUP=/root/veci-sms-ui-exact-live-v12-backup",
                              "BACKUP="+str(self.backup))
        script=script.replace("/tmp/sysinfo/board_name",str(self.board))
        script=script.replace("$(id -u)", "0")
        script=script.replace("df -k /overlay","df -k "+str(self.root))
        script=script.replace("df -h /overlay","df -h "+str(self.root))
        self.output.write_text(script)
        wget=self.bin/"wget"
        wget.write_text("#!/bin/sh\n"
                        "test \"$1\" = '-q' || exit 3\n"
                        "test \"$2\" = '-O' || exit 3\n"
                        "cp \""+str(PATCH)+"\" \"$3\"\n")
        wget.chmod(0o755)
        self.env=dict(os.environ,PATH=str(self.bin)+":"+os.environ["PATH"])

    def run_script(self,action):
        return subprocess.run(["sh",str(self.output),action],text=True,
                              capture_output=True,env=self.env,timeout=10)

    def test_shell_syntax(self):
        result=subprocess.run(["sh","-n",str(INSTALLER)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_patch_digest_and_source_pin(self):
        s=INSTALLER.read_text()
        self.assertIn("ORIGINAL_SHA="+ORIGINAL_SHA,s)
        self.assertIn("PATCHED_SHA="+PATCHED_SHA,s)
        self.assertIn("PATCH_COMMIT=9c5be87354cb08b93ef478fdd2dbd1b7e777fc7b",s)
        self.assertNotIn("/usr/sbin/we5927-at",s)
        self.assertNotIn("sysupgrade ",s)
        self.assertNotIn("uci set ",s)
        self.assertNotIn("ubus call",s)
        self.assertNotIn("AT+CMGL=4' 5000",s)

    def test_refuse_changed_file_before_touching_backup(self):
        self.page.write_text("CUSTOM!\n")
        r=self.run_script("apply")
        self.assertNotEqual(r.returncode,0)
        self.assertIn("unexpected_local_cellular_file_unchanged",r.stderr)
        self.assertEqual(self.page.read_text(),"CUSTOM!\n")
        self.assertFalse(self.backup.exists())

    def test_simulate_apply_rollback_and_preserve_original(self):
        # Immutable expected original is reconstructed by removing only
        # two appended blocks from the exact operator-captured patched source.
        s=PATCH.read_text()
        p=s.index('\t\t\t<section class="panel" aria-labelledby="cellular-sms-count-title">')
        q=s.index('\t\t\t<div class="notice-card">',p)
        s=s[:p]+s[q:]
        p=s.index("\t\t// The existing v2 endpoint reads AT+CPMS? only.")
        q=s.index("\t\tconst reconnect = root.querySelector",p)
        s=s[:p]+s[q:]
        orig=s.encode()
        self.assertEqual(hashlib.sha256(orig).hexdigest(),ORIGINAL_SHA)
        self.page.write_bytes(orig)
        first=self.run_script("apply")
        self.assertEqual(first.returncode,0,first.stderr)
        self.assertIn("V12_UI_ASSETS_LIVE_PASS",first.stdout)
        self.assertEqual(self.page.read_bytes(),self.patch)
        self.assertEqual((self.backup/"original.js").read_bytes(),orig)
        self.assertEqual(hashlib.sha256(self.page.read_bytes()).hexdigest(),PATCHED_SHA)
        second=self.run_script("apply")
        self.assertNotEqual(second.returncode,0)
        self.assertIn("backup_exists_no_overwrite",second.stderr)
        rolled=self.run_script("rollback")
        self.assertEqual(rolled.returncode,0,rolled.stderr)
        self.assertIn("V12_UI_ROLLBACK_PASS",rolled.stdout)
        self.assertEqual(self.page.read_bytes(),orig)

    def test_no_overwrite_after_newer_local_edit(self):
        s=PATCH.read_text()
        p=s.index('\t\t\t<section class="panel" aria-labelledby="cellular-sms-count-title">')
        q=s.index('\t\t\t<div class="notice-card">',p)
        s=s[:p]+s[q:]
        p=s.index("\t\t// The existing v2 endpoint reads AT+CPMS? only.")
        q=s.index("\t\tconst reconnect = root.querySelector",p)
        self.page.write_text(s[:p]+s[q:])
        self.assertEqual(self.run_script("apply").returncode,0)
        self.page.write_text(self.page.read_text()+"\n// custom local edit\n")
        r=self.run_script("rollback")
        self.assertNotEqual(r.returncode,0)
        self.assertIn("newer_local_change_detected_no_overwrite",r.stderr)
        self.assertTrue(self.page.read_text().endswith("// custom local edit\n"))

if __name__=="__main__":
    unittest.main()
