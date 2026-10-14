"""Offline atomic stage / verify / rollback checks. Never touches a router."""
import hashlib
import os
import pathlib
import re
import shutil
import subprocess
import tarfile
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
SOURCE=ROOT/"scripts/veci-sms-v161-inactive-stage-install.sh"
PIN="4f8b5070443bf0eebf036d502d2ff0f852ffa32c"
NAMES=("cellular.js","rpcd-veci.sms","veci-sms-cmgs",
       "veci-sms-status-report","veci-sms-send-one",
       "veci-sms-delivery-map","veci-sms-sent-delivery-view",
       "veci-sms-report-ingest")
class StageBundle(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.d=pathlib.Path(self.temp.name)
        d=self.d
        (d/"bin").mkdir()
        (d/"board").write_text("zbtlink,zbt-we5927")
        (d/"feature").write_text("1")
        (d/"live-baseline").write_text("verified")
        payload=d/"payload"/"veci-v161"
        payload.mkdir(parents=True)
        for name in NAMES:
            f=payload/name
            f.write_text("test fixture for "+name+"\n")
        checksums=[]
        for name in sorted(NAMES):
            digest=hashlib.sha256((payload/name).read_bytes()).hexdigest()
            checksums.append(f"{digest}  {name}\n")
        (payload/"SHA256SUMS").write_text("".join(checksums))
        (payload/"RELEASE_INFO").write_text(
          "STAGE_ONLY=1\nNO_MODEM_COMMANDS=1\nNO_AUTO_ACTIVATION=1\nSOURCE_COMMIT="+PIN+"\n")
        self.bundle=d/"offline.tar.gz"
        with tarfile.open(self.bundle,"w:gz") as archive:
            archive.add(payload,arcname="veci-v161")
        digest=hashlib.sha256(self.bundle.read_bytes()).hexdigest()
        mock=d/"bin"/"wget"
        mock.write_text("""#!/bin/sh
[ "$1" = "-qO" ] && [ "$3" = bundle:local ] || exit 9
cp "$FIXTURE_BUNDLE" "$2"
""")
        mock.chmod(0o700)
        src=SOURCE.read_text()
        self.assertNotIn("AT+CNMI=",src)
        self.assertNotIn("AT+CMGS=",src)
        self.assertNotIn("/etc/init.d/rpcd restart",src)
        for old,new in [
           ("STAGE=/root/veci-v161-stage","STAGE="+str(d/"stage")),
           ("FLAG=/etc/veci-sms-feature","FLAG="+str(d/"feature")),
           ("/tmp/sysinfo/board_name",str(d/"board")),
           ('[ "$(id -u)" = 0 ]','[ 0 = 0 ]'),
           ('$(uname -r)','$(printf 6.12.94)'),
           ("BUNDLE_SHA=351ae4c239f37d62e4e2694dcdc487d763acd9bf7a5ac386e6e94bec06a68738",
            "BUNDLE_SHA="+digest),
           ("URL=https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/download/veci-sms-v161-stage-4f8b5070443b/veci-v161-stage.tar.gz",
            "URL=bundle:local"),
           ('dest="/root/.veci-v161-stage.$$"','dest="'+str(d/".stage")+'.$$"'),
           ("df -k /overlay","df -k /"),
        ]:
           self.assertIn(old,src,old)
           src=src.replace(old,new)
        start=src.index("live_ok(){")
        end=src.index("\nmanifest_in(){",start)
        src=src[:start]+'live_ok(){ [ -f "'+str(d/"live-baseline")+'" ]; }\n'+src[end:]
        self.script=d/"stager"
        self.script.write_text(src)
        self.script.chmod(0o700)
        self.env=os.environ.copy()
        self.env["FIXTURE_BUNDLE"]=str(self.bundle)
        self.env["PATH"]=str(d/"bin")+os.pathsep+self.env.get("PATH","")
    def tearDown(self):
        self.temp.cleanup()
    def run_stage(self,operation):
        return subprocess.run(["sh",str(self.script),operation],
             capture_output=True,text=True,env=self.env,timeout=12)
    def test_stage_status_and_rollback_without_touching_live_baseline(self):
        cp=self.run_stage("status")
        self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
        self.assertIn("VECI_V161_INACTIVE_STAGE=absent_or_invalid",cp.stdout)
        self.assertIn("VECI_V161_ACTIVATED=false",cp.stdout)
        cp=self.run_stage("stage")
        self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
        self.assertIn("VECI_V161_INACTIVE_STAGING_PASS",cp.stdout)
        self.assertEqual(sorted(p.name for p in (self.d/"stage").iterdir()),
                         sorted([*NAMES,"SHA256SUMS","RELEASE_INFO"]))
        self.assertIn("VECI_V161_INACTIVE_STAGE=verified",self.run_stage("status").stdout)
        again=self.run_stage("stage")
        self.assertEqual(again.returncode,0)
        self.assertIn("ALREADY_PRESENT_PASS",again.stdout)
        rollback=self.run_stage("rollback")
        self.assertEqual(rollback.returncode,0,rollback.stdout+rollback.stderr)
        self.assertIn("VECI_V161_INACTIVE_STAGING_ROLLBACK_PASS",rollback.stdout)
        self.assertFalse((self.d/"stage").exists())
        self.assertEqual((self.d/"live-baseline").read_text(),"verified")
    def test_modified_payload_blocks_rollback(self):
        self.assertEqual(self.run_stage("stage").returncode,0)
        (self.d/"stage"/"veci-sms-cmgs").write_text("tampered")
        cp=self.run_stage("rollback")
        self.assertNotEqual(cp.returncode,0)
        self.assertTrue((self.d/"stage").exists())
    def test_bundle_tamper_never_installs(self):
        with self.bundle.open("ab") as f:
            f.write(b"corrupt")
        cp=self.run_stage("stage")
        self.assertNotEqual(cp.returncode,0)
        self.assertIn("bundle_checksum",cp.stderr)
        self.assertFalse((self.d/"stage").exists())
    def test_live_baseline_mismatch_aborts_before_download(self):
        (self.d/"live-baseline").unlink()
        cp=self.run_stage("stage")
        self.assertNotEqual(cp.returncode,0)
        self.assertIn("live_baseline_changed",cp.stderr)
        self.assertFalse((self.d/"stage").exists())
    def test_sms_off_setting_is_preserved(self):
        # A staging-only archive is passive regardless of the existing switch.
        cp=self.run_stage("stage")
        self.assertEqual(cp.returncode,0)
        self.assertEqual((self.d/"feature").read_text(),"1")
        self.assertFalse((self.d/"stage"/"secret").exists())

if __name__=="__main__":
    unittest.main()
