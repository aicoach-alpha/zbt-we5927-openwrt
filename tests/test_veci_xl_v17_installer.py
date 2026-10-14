"""Offline transactional XL USSD overlay tests. NO modem/router/network access."""
import hashlib
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"scripts/veci-xl-v17-ussd-quota-install.sh"
FILES=("veci-xl-ussd-once","veci-xl-ussd","veci-xl-quota-cache","veci.ussd","veci-xl-ussd.json","cellular.js")

class XLInstaller(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.d=Path(self.tmp.name)
        self.live=self.d/"live";self.live.mkdir()
        self.ui=self.live/"cellular.js";self.ui.write_text("LIVE_SMS_V160\n")
        self.cmgs=self.live/"veci-sms-cmgs";self.cmgs.write_text("SMS_V160_BINARY\n")
        self.paths={name:self.live/name for name in FILES if name!="cellular.js"}
        self.back=self.d/"backup"
        self.fixture=self.d/"package";self.fixture.mkdir()
        body=self.fixture/"veci-xl-v17";body.mkdir()
        self.expected={}
        for name in FILES:
            (body/name).write_text("V17:"+name+"\n")
            self.expected[name]=self.digest(body/name)
        (body/"SHA256SUMS").write_text("".join(
           self.expected[n]+"  "+n+"\n" for n in FILES))
        (body/"RELEASE_INFO").write_text("VERSION=v1.7.1-xl-ussd\n")
        self.tar=self.d/"bundle.tar.gz"
        with tarfile.open(self.tar,"w:gz") as z:
            z.add(body,arcname="veci-xl-v17")
        b=self.d/"bin";b.mkdir()
        for name,code in {
         "wget":'''#!/bin/sh
[ "$1" = "-qO" ] || exit 2
cp "$TEST_BUNDLE" "$2"
''',
         "ubus":'''#!/bin/sh
if [ "$3" = veci.sms ];then exit 0;fi
[ -e "$TEST_FAIL_UBUS" ] && exit 2
if [ -f "$TEST_DELAY_UBUS" ];then
 n="$(cat "$TEST_DELAY_UBUS")"
 if [ "$n" -gt 0 ];then
  echo "$((n-1))" > "$TEST_DELAY_UBUS"
  exit 2
 fi
fi
[ "$1" = -S ] && [ "$2" = list ] && [ "$3" = veci.ussd ]
''',
         "sleep":'''#!/bin/sh
exit 0
''',
         "restart-rpcd":'''#!/bin/sh
echo restart >> "$TEST_DIR/restarted"
exit 0
'''
        }.items():
            f=b/name;f.write_text(code);f.chmod(0o700)
        script=SOURCE.read_text()
        replacements={
           "UI=/www/veci/js/pages/cellular.js":"UI="+str(self.ui),
           "CMGS=/usr/libexec/veci-sms-cmgs":"CMGS="+str(self.cmgs),
           "WRAPPER=/usr/libexec/veci-xl-ussd":"WRAPPER="+str(self.paths["veci-xl-ussd"]),
           "CACHE=/usr/libexec/veci-xl-quota-cache":"CACHE="+str(self.paths["veci-xl-quota-cache"]),
           "NATIVE=/usr/libexec/veci-xl-ussd-once":"NATIVE="+str(self.paths["veci-xl-ussd-once"]),
           "RPC=/usr/libexec/rpcd/veci.ussd":"RPC="+str(self.paths["veci.ussd"]),
           "ACL=/usr/share/rpcd/acl.d/veci-xl-ussd.json":"ACL="+str(self.paths["veci-xl-ussd.json"]),
           "BACK=/root/veci-xl-v17-rollback":"BACK="+str(self.back),
           "OLD_UI=be7706e19a6e1548cfb63a1e29c95da5ce67a8934f274bbd44d4edfd9aea2aef":
              "OLD_UI="+self.digest(self.ui),
           "OLD_CMGS=ccb6f066f0be2fa0fbb5131a98f90ded88e28ae0442a57d0d73b1949b07016fb":
              "OLD_CMGS="+self.digest(self.cmgs),
           "PIN=f59f566c964f5dee70ce246c37a78e0a9eca01a16d1c530588adc6aebd23900c":
              "PIN="+self.digest(self.tar),
           "[ \"$(id -u)\" = 0 ]":"[ 0 = 0 ]",
           "\"$(cat /tmp/sysinfo/board_name 2>/dev/null || :)\"":"\"zbtlink,zbt-we5927\"",
           "\"$(uname -r)\"":"\"6.12.94\"",
           "/etc/init.d/rpcd restart":str(b/"restart-rpcd"),
           "df -k /overlay":"df -k /",
           "URL=https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/download/veci-xl-v17-fbf0fc346a1b/veci-xl-v17.tar.gz":
              "URL=fixture:test",
        }
        for old,new in replacements.items():
            self.assertIn(old,script,old)
            script=script.replace(old,new)
        self.script=self.d/"installer"
        self.script.write_text(script);self.script.chmod(0o700)
        self.env=os.environ.copy()
        self.env["PATH"]=str(b)+os.pathsep+self.env.get("PATH","")
        self.env["TEST_BUNDLE"]=str(self.tar)
        self.env["TEST_DIR"]=str(self.d)
        self.env["TEST_FAIL_UBUS"]=str(self.d/"fail_ubus")
        self.env["TEST_DELAY_UBUS"]=str(self.d/"delay_ubus")
    def tearDown(self):self.tmp.cleanup()
    @staticmethod
    def digest(file):return hashlib.sha256(file.read_bytes()).hexdigest()
    def call(self,arg):
        return subprocess.run(["sh",str(self.script),arg],text=True,capture_output=True,
                              env=self.env,timeout=10)
    def test_exact_live_preserved_and_rollback(self):
        cp=self.call("apply")
        self.assertEqual(cp.returncode,0,cp.stderr+cp.stdout)
        self.assertIn("VECI_XL_USSD_V17_FILES_AND_RPC_LIVE_PASS",cp.stdout)
        for n in FILES:self.assertEqual(self.digest(self.ui if n=="cellular.js" else self.paths[n]),self.expected[n])
        self.assertEqual(self.cmgs.read_text(),"SMS_V160_BINARY\n")
        cp=self.call("rollback")
        self.assertEqual(cp.returncode,0,cp.stderr+cp.stdout)
        self.assertEqual(self.ui.read_text(),"LIVE_SMS_V160\n")
        self.assertTrue(all(not p.exists() for p in self.paths.values()))
        self.assertEqual(self.cmgs.read_text(),"SMS_V160_BINARY\n")
    def test_router_service_failure_rolls_back(self):
        (self.d/"fail_ubus").write_text("1")
        cp=self.call("apply")
        self.assertNotEqual(cp.returncode,0)
        self.assertIn("AUTOROLLBACK=PASS",cp.stderr)
        self.assertEqual(self.ui.read_text(),"LIVE_SMS_V160\n")
        self.assertTrue(all(not p.exists() for p in self.paths.values()))
    def test_register_waits_for_delayed_rpcd_discovery(self):
        (self.d/"delay_ubus").write_text("3")
        cp=self.call("apply")
        self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
        self.assertEqual((self.d/"delay_ubus").read_text().strip(),"0")
        self.assertIn("VECI_XL_USSD_V17_FILES_AND_RPC_LIVE_PASS",cp.stdout)

    def test_reapply_after_verified_automatic_rollback(self):
        (self.d/"fail_ubus").write_text("1")
        failed=self.call("apply")
        self.assertNotEqual(failed.returncode,0)
        self.assertIn("AUTOROLLBACK=PASS",failed.stderr)
        self.assertTrue(self.back.is_dir())
        (self.d/"fail_ubus").unlink()
        ok=self.call("apply")
        self.assertEqual(ok.returncode,0,ok.stdout+ok.stderr)
        self.assertIn("FILES_AND_RPC_LIVE_PASS",ok.stdout)
        self.assertEqual(self.cmgs.read_text(),"SMS_V160_BINARY\\n")

    def test_tampered_rollback_backup_stays_blocked(self):
        (self.d/"fail_ubus").write_text("1")
        failed=self.call("apply")
        self.assertNotEqual(failed.returncode,0)
        (self.d/"fail_ubus").unlink()
        (self.back/"ui").write_text("tampered")
        cp=self.call("apply")
        self.assertNotEqual(cp.returncode,0)
        self.assertIn("preexisting_backup_invalid",cp.stderr)
        self.assertEqual(self.ui.read_text(),"LIVE_SMS_V160\\n")

    def test_modified_baseline_blocks_install(self):
        self.ui.write_text("unexpected user modification")
        cp=self.call("apply")
        self.assertNotEqual(cp.returncode,0)
        self.assertIn("v160_ui_or_sms_transport_changed",cp.stderr)
        self.assertFalse(self.back.exists())
    def test_corrupt_archive_aborts_without_changes(self):
        with self.tar.open("ab") as f:f.write(b"tamper")
        cp=self.call("apply")
        self.assertNotEqual(cp.returncode,0)
        self.assertIn("bundle_digest",cp.stderr)
        self.assertEqual(self.ui.read_text(),"LIVE_SMS_V160\n")
        self.assertTrue(all(not p.exists() for p in self.paths.values()))
    def test_idempotent_install(self):
        self.assertEqual(self.call("apply").returncode,0)
        cp=self.call("apply")
        self.assertEqual(cp.returncode,0)
        self.assertIn("ALREADY_INSTALLED_PASS",cp.stdout)
    def test_active_files_modified_blocks_unsafe_rollback(self):
        self.assertEqual(self.call("apply").returncode,0)
        self.paths["veci-xl-ussd"].write_text("someone updated it")
        cp=self.call("rollback")
        self.assertNotEqual(cp.returncode,0)
        self.assertIn("active_files_not_verified",cp.stderr)
        self.assertTrue(self.back.exists())

if __name__=="__main__":unittest.main()
