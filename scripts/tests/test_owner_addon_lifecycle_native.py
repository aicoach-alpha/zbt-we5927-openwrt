"""Reuse existing DDNS/SQM procd service and provisioned portal/voucher UCI switches.

Runs existing, original VeCI UAT scripts with native UCI/libubox in sandbox.
Never starts an actual addon, reloads wifi, or installs packages.
"""
import json,os,subprocess,sys,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
R=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime"
U=ROOT/"rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2"
HOST_UCI=os.environ.get("VECI_HOST_UCI") or ""
PREFIX=Path(os.environ.get("VECI_LIBUBOX_PREFIX") or "/missing-native-libubox")

class OriginalAddonLifecycle(unittest.TestCase):
    def run_script(self,script,*args):
        self.assertTrue(HOST_UCI and Path(HOST_UCI).is_file(),"Native host UCI required")
        self.assertTrue((PREFIX/"share/libubox/jshn.sh").is_file())
        env={**os.environ,"PATH":str(PREFIX/"bin")+":"+os.environ.get("PATH",""),
             "LD_LIBRARY_PATH":str(PREFIX/"lib")+":"+os.environ.get("LD_LIBRARY_PATH","")}
        p=subprocess.run([sys.executable,str(ROOT/"scripts/uat"/script),*args],
            cwd=ROOT,env=env,capture_output=True,text=True,timeout=80)
        self.assertEqual(p.returncode,0,p.stdout+"\n"+p.stderr)
        self.assertIn("PASS",p.stdout)
    def test_existing_ddns_sqm_apk_owned_startup_procd(self):
        self.run_script("test-owner-addon-services-host.py",str(PREFIX))
    def test_existing_wireguard_guest_voucher_native_uci_switches(self):
        self.run_script("test-addon-profiles-host.py",HOST_UCI,str(PREFIX))
    def test_acl_ui_and_no_duplicate_modem_control(self):
        acl=json.loads((R/"veci2-addon-acl.json").read_text())["veci-v2-addon-admin"]
        self.assertEqual(acl["read"]["ubus"]["veci.v2.addon"],["status"])
        self.assertEqual(set(acl["write"]["ubus"]["veci.v2.addon"]),
                         {"setVpnStartup","setPortalStartup"})
        addon=(R/"veci2-addon").read_text()
        helper=(R/"veci2-addon-profiles").read_text()
        sv=(R/"veci2-services").read_text()
        self.assertIn("setPortalStartup",addon)
        self.assertIn("set_portal_startup",helper)
        self.assertIn("apk info -L",sv)
        self.assertIn("ddns-scripts",sv)
        self.assertIn("sqm-scripts",sv)
        self.assertIn("protected_service",sv)
        self.assertNotIn("AT+CFUN",sv+helper+addon)
        ui=(U/"addon-profiles.js").read_text()
        self.assertIn("setPortalStartup",ui)
        self.assertIn("window.confirm",ui)
        self.assertIn("ENABLE_PORTAL_AP",ui)
        self.assertIn("REQUIRE_VOUCHER",ui)
        for rel in ("veci2-services","veci2-addon","veci2-addon-profiles"):
            subprocess.run(["busybox","ash","-n",str(R/rel)],check=True,capture_output=True,timeout=5)
        for name in ("services.js","addon-profiles.js"):
            subprocess.run(["node","--check",str(U/name)],check=True,capture_output=True,timeout=5)

if __name__=="__main__":unittest.main()
