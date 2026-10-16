"""J9D negative tests. All shell simulations use temporary files; no router access."""
import pathlib
import re
import shlex
import subprocess
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
CORE=ROOT/"source/veci.commit"
GUEST=ROOT/"source/veci-app-guest/files/usr/libexec/rpcd/veci.app.guest"
VOUCHER=ROOT/"source/veci-app-voucher/files/usr/libexec/rpcd/veci.app.voucher"
WG=ROOT/"source/veci-app-wireguard/files/usr/libexec/rpcd/veci.app.wireguard"

def section(text,name):
    m=re.search(r"(?ms)^"+re.escape(name)+r"\(\) \{\n.*?^\}",text)
    if not m: raise AssertionError("function not found "+name)
    return m.group()

def shell(source,env=None):
    return subprocess.run(["sh","-c",source],capture_output=True,text=True,env=env,timeout=12)

class J9DNegativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The CI workflow prepares pinned VeCI Core to the exact path.
        cls.core=pathlib.Path("/tmp/j9d-openwrt/package/veci/files/rpcd-veci").read_text()

    def test_all_scripts_parse(self):
        for p in (GUEST,VOUCHER,WG,pathlib.Path("/tmp/j9d-openwrt/package/veci/files/rpcd-veci")):
            with self.subTest(p=p.name):
                r=subprocess.run(["sh","-n",str(p)],capture_output=True,text=True)
                self.assertEqual(r.returncode,0,r.stderr)

    def test_expired_or_future_firmware_token_rejected(self):
        fn=section(self.core,"firmware_validation_fresh")
        src='firmware_validation_max_age=600\n'+fn+'\ndate() { printf "2000\\n"; }\n'
        for issued,expected in [("2000",0),("1400",0),("1399",1),("2001",1),("",1),("garbled",1)]:
            with self.subTest(issued=issued):
                r=shell(src+"firmware_validation_fresh "+shlex.quote(issued))
                self.assertEqual(r.returncode,expected,r.stderr)
        self.assertIn('firmware_validation_fresh "$validation_issued"',section(self.core,"method_firmware_apply"))
        self.assertIn('rm -f "$firmware_validation_meta"',section(self.core,"method_firmware_apply"))
        self.assertIn('firmware_validation_fresh "$validation_issued"',section(self.core,"method_firmware_status"))

    def test_empty_cleanup_ack_must_not_remove_package(self):
        fn=section(self.core,"method_app_action")
        with tempfile.TemporaryDirectory() as d:
            temp=pathlib.Path(d)
            (temp/"guest.json").write_text('{"id":"guest"}')
            fn=fn.replace('/usr/share/veci/apps/',str(temp)+'/')
            src=(
                'jsonfilter() { case "$*" in *"@.id"*) printf guest;; *"@.action"*) printf remove;; *"@.ok"*) printf false;; esac; }\n'
                'clean_token() { printf "%s" "$1"; }\n'
                'package_manager() { printf apk; }\n'
                'manifest_remove_packages() { printf "veci-app-guest\\n"; }\n'
                'safe_package_words() { return 0; }\n'
                'ubus() { case "$1" in list) printf "veci.app.guest\\n";; call) return 0;; esac; }\n'
                'apk() { touch '+shlex.quote(str(temp/"WRONG_PACKAGE_REMOVAL"))+'; }\n'
                +fn+'\nprintf "{\\"id\\":\\"guest\\",\\"action\\":\\"remove\\"}" | method_app_action\n'
            )
            r=shell(src)
            self.assertIn("app_cleanup_failed",r.stdout)
            self.assertFalse((temp/"WRONG_PACKAGE_REMOVAL").exists())
            self.assertIn("app_cleanup_provider_missing",fn)
            self.assertIn("app_cleanup_unavailable",fn)

    def test_guest_snapshot_restores_files_after_fault(self):
        text=GUEST.read_text()
        functions=["portal_snapshot_begin","portal_snapshot_discard","portal_snapshot_restore"]
        with tempfile.TemporaryDirectory() as d:
            testdir=pathlib.Path(d)/"config";testdir.mkdir()
            for name in ("network","dhcp","firewall","wireless","uhttpd","uspot","veci_guest"):
                (testdir/name).write_text("ORIGINAL:"+name+"\n")
            src="\n".join(section(text,n) for n in functions).replace("/etc/config/",str(testdir)+"/")
            src+=('\nuci() { return 0; }\nwifi() { return 0; }\nservice_restart() { return 0; }\n'
                'portal_snapshot_begin || exit 10\n'
                'printf "BROKEN\\n" > '+shlex.quote(str(testdir/"firewall"))+'\n'
                'portal_snapshot_restore || exit 20\n'
                'test "$GUEST_ROLLBACK_REASON" = activation_failed_rolled_back\n'
            )
            r=shell(src)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            self.assertEqual((testdir/"firewall").read_text(),"ORIGINAL:firewall\n")
        self.assertIn("portal_snapshot_begin || return 1",section(text,"enable_portal"))
        self.assertIn("portal_snapshot_restore",section(text,"enable_portal"))
        self.assertIn("portal_snapshot_begin || return 1",section(text,"provision_portal"))

    def test_voucher_status_does_not_mutate(self):
        status=section(VOUCHER.read_text(),"method_status")
        self.assertNotIn("cleanup_expired",status.replace("# Read-only. Expiry cleanup belongs to the background cleaner or\n\t# explicit cleanupExpired write method, never a status poll.",""))
        self.assertIn('cleanupExpired) method_cleanup',VOUCHER.read_text())
        self.assertIn('[ "$expires" -gt "$now" ]',status)

    def test_wireguard_must_not_enable_peer_routes(self):
        create=section(WG.read_text(),"method_create")
        self.assertIn('route_allowed_ips=0',create)
        self.assertNotIn('route_allowed_ips=1',create)
        self.assertIn('0.0.0.0/0|::/0',create)

    def test_flash_and_live_uat_remain_blocked(self):
        doc=(ROOT/"docs/J9C-HARDWARE-UAT.md").read_text()
        self.assertIn("NO_GO",doc)
        self.assertRegex(CORE.read_text().strip(),r"^[0-9a-f]{40}$")

if __name__=="__main__":
    unittest.main()
