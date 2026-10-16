"""No-router no-network test of optional SMS Inbox 1.3 installer/rollback."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
INSTALLER=ROOT/"scripts/veci-sms-inbox-admin-ui-v13-install.sh"
UI=ROOT/"scripts/veci-sms-inbox-ui-staged-20261013/cellular.js"
PACKAGE=ROOT/"source/veci-sms-inbox-we5927/files"
RPC=PACKAGE/"usr/libexec/rpcd/veci.sms"
WORKER=PACKAGE/"usr/libexec/veci-sms-inbox-index"
ACL=PACKAGE/"usr/share/rpcd/acl.d/veci-sms-inbox-we5927.json"
V12=ROOT/"scripts/veci-sms-ui-live-captured-20261012/cellular.js"
SHA_V12="2deb013e6ccf433b9c3abc3d7f02aafb33739dd1b5b5f222d4de501865314d40"

class OptionalInstaller(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.base=self.root/"www/veci/js/pages/cellular.js"
        self.rpc=self.root/"usr/libexec/rpcd/veci.sms"
        self.worker=self.root/"usr/libexec/veci-sms-inbox-index"
        self.acl=self.root/"usr/share/rpcd/acl.d/veci-sms-inbox-we5927.json"
        self.backup=self.root/"backups/v13"
        for p in (self.base,self.rpc,self.worker,self.acl,self.backup):
            p.parent.mkdir(parents=True,exist_ok=True)
        self.base.write_bytes(V12.read_bytes())
        self.board=self.root/"sysinfo/board_name"
        self.board.parent.mkdir()
        self.board.write_text("zbtlink,zbt-we5927\n")
        self.fake_rpcd=self.root/"fake-rpcd"
        self.fake_rpcd.write_text("#!/bin/sh\necho restart >> '"+str(self.root/"restarts")+"'\n")
        self.fake_rpcd.chmod(0o700)
        self.bin=self.root/"bin"
        self.bin.mkdir()
        wget=self.bin/"wget"
        script=(
            "#!/bin/sh\n"
            '[ "$1" = "-q" ] && [ "$2" = "-O" ] || exit 12\n'
            'case "$4" in\n'
            "  */scripts/veci-sms-inbox-ui-staged-20261013/cellular.js) cp '"+str(UI)+"' \"$3\" ;;\n"
            "  */usr/libexec/rpcd/veci.sms) cp '"+str(RPC)+"' \"$3\" ;;\n"
            "  */usr/libexec/veci-sms-inbox-index) cp '"+str(WORKER)+"' \"$3\" ;;\n"
            "  */usr/share/rpcd/acl.d/veci-sms-inbox-we5927.json) cp '"+str(ACL)+"' \"$3\" ;;\n"
            "  *) exit 13 ;;\n"
            "esac\n"
        )
        wget.write_text(script)
        wget.chmod(0o700)
        ubus=self.bin/"ubus"
        ubus.write_text("#!/bin/sh\n[ \"$1\" = list ] && [ \"$2\" = veci.sms ] || exit 11\necho veci.sms\n")
        ubus.chmod(0o700)
        self.env={**os.environ,"PATH":str(self.bin)+":"+os.environ["PATH"]}
        src=INSTALLER.read_text()
        substitutions={
          "BASE=/www/veci/js/pages/cellular.js":"BASE="+str(self.base),
          "RPC=/usr/libexec/rpcd/veci.sms":"RPC="+str(self.rpc),
          "WORKER=/usr/libexec/veci-sms-inbox-index":"WORKER="+str(self.worker),
          "ACL=/usr/share/rpcd/acl.d/veci-sms-inbox-we5927.json":"ACL="+str(self.acl),
          "BACKUP=/root/veci-sms-inbox-v13-rollback":"BACKUP="+str(self.backup),
          "/tmp/sysinfo/board_name":str(self.board),
          "[ -x /etc/init.d/rpcd ]":"[ -x '"+str(self.fake_rpcd)+"' ]",
          "/etc/init.d/rpcd restart":"sh '"+str(self.fake_rpcd)+"' restart",
          "df -h /overlay":"df -h "+str(self.root),
          "df -k /overlay":"df -k "+str(self.root),
          '$(id -u)':'0'
        }
        for key,value in substitutions.items():
            if key not in src:
                raise AssertionError("Missing installer fragment: "+key)
            src=src.replace(key,value)
        self.installer=self.root/"install.sh"
        self.installer.write_text(src)

    def exec(self,action):
        return subprocess.run(["sh",str(self.installer),action],text=True,
                              capture_output=True,timeout=12,env=self.env)

    def test_shell_syntax_and_actual_asset_sha_integrity(self):
        p=subprocess.run(["sh","-n",str(INSTALLER)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        s=INSTALLER.read_text()
        for name,path in (("V13_SHA",UI),("RPC_SHA",RPC),("WORKER_SHA",WORKER),("ACL_SHA",ACL)):
            self.assertIn(name+"="+hashlib.sha256(path.read_bytes()).hexdigest(),s)
        self.assertEqual(hashlib.sha256(V12.read_bytes()).hexdigest(),SHA_V12)

    def test_safe_status_before_install(self):
        p=self.exec("status")
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn("EXPECTED_V12_SHA="+SHA_V12,p.stdout)
        self.assertIn("INBOX_RPC=absent",p.stdout)
        self.assertFalse(self.backup.exists())

    def test_unknown_ui_rejected_with_no_side_effect(self):
        self.base.write_text("CUSTOM UPDATED UI")
        p=self.exec("apply")
        self.assertNotEqual(p.returncode,0)
        self.assertIn("current_cellular_not_live_v12",p.stderr)
        self.assertEqual(self.base.read_text(),"CUSTOM UPDATED UI")
        self.assertFalse(self.backup.exists())
        self.assertFalse(self.rpc.exists())
        self.assertFalse((self.root/"restarts").exists())

    def test_mock_apply_and_rollback_never_run_sms_worker(self):
        p=self.exec("apply")
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn("VECI_INBOX_V13_ASSETS_PASS",p.stdout)
        self.assertEqual(self.base.read_bytes(),UI.read_bytes())
        self.assertEqual(self.rpc.read_bytes(),RPC.read_bytes())
        self.assertEqual(self.worker.read_bytes(),WORKER.read_bytes())
        self.assertEqual(self.acl.read_bytes(),ACL.read_bytes())
        self.assertEqual((self.backup/"cellular-v12.js").read_bytes(),V12.read_bytes())
        self.assertEqual((self.root/"restarts").read_text().count("restart"),1)
        p=self.exec("apply")
        self.assertNotEqual(p.returncode,0)
        p=self.exec("rollback")
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn("VECI_INBOX_V13_ROLLBACK_PASS",p.stdout)
        self.assertEqual(self.base.read_bytes(),V12.read_bytes())
        self.assertFalse(self.rpc.exists())
        self.assertFalse(self.worker.exists())
        self.assertFalse(self.acl.exists())
        self.assertEqual((self.root/"restarts").read_text().count("restart"),2)

    def test_registration_failure_automatically_restores_v12(self):
        ubus=self.bin/"ubus"
        ubus.write_text("#!/bin/sh\nexit 1\n")
        p=self.exec("apply")
        self.assertNotEqual(p.returncode,0)
        self.assertIn("rpc_registration_not_visible",p.stderr)
        self.assertIn("INBOX_V13_AUTOMATIC_ROLLBACK_STARTED",p.stderr)
        self.assertEqual(self.base.read_bytes(),V12.read_bytes())
        self.assertFalse(self.rpc.exists())
        self.assertFalse(self.worker.exists())
        self.assertFalse(self.acl.exists())
        self.assertEqual((self.root/"restarts").read_text().count("restart"),2)

    def test_unknown_postinstall_changes_refuse_rollback(self):
        self.assertEqual(self.exec("apply").returncode,0)
        self.base.write_text("other developer patch")
        p=self.exec("rollback")
        self.assertNotEqual(p.returncode,0)
        self.assertIn("newer_ui_change_do_not_overwrite",p.stderr)
        self.assertEqual(self.base.read_text(),"other developer patch")

    def test_backend_source_safety(self):
        s=INSTALLER.read_text()
        self.assertIn("MODEM_SMS_NOT_ACCESSED_BY_INSTALLER",s)
        for command in ("/usr/sbin/we5927-at /dev", "AT+CMGL=4' 5000", "AT+CUSD=1'",
                        "sysupgrade ", "uci set ", "/etc/init.d/we5927-lte restart",
                        "/etc/init.d/uhttpd restart"):
            self.assertNotIn(command,s)
        self.assertIn("BACKUP=/root/veci-sms-inbox-v13-rollback",s)
        self.assertIn("V12_SHA="+SHA_V12,s)

if __name__=="__main__":
    unittest.main()
