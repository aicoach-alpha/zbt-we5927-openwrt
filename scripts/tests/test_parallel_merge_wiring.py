"""Cross-track packaging and ACL checks. Source-only: not hardware UAT."""
from pathlib import Path
import json,re,subprocess,unittest

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/"rebuild/veci-v2/packages"
RT=BASE/"veci-v2-runtime"
UI=BASE/"veci-v2-ui"
V6=BASE/"veci-v2-ipv6"
INDEX=(UI/"files/www/veci2/index.html").read_text()
APP=(UI/"files/www/veci2/app.js").read_text()
RMAKE=(RT/"Makefile").read_text()
UMAKE=(UI/"Makefile").read_text()
VMAKE=(V6/"Makefile").read_text()


class ParallelMergeWiring(unittest.TestCase):
    def test_all_7_new_module_controls_are_wired(self):
        self.assertIn("veci2-ra",VMAKE)
        for name in ("cron","services"):
            self.assertIn("veci2-"+name,RMAKE)
            self.assertIn("veci2-"+name+"-acl.json",RMAKE)
        self.assertIn("veci2-wifi-controls",RMAKE)
        self.assertIn("veci2-backup",UMAKE)
        for name in ("ipv6-ra","wifi-controls","cron","services","backup"):
            self.assertIn('src="/veci2/'+name+'.js"',INDEX)
            self.assertIn("./files/www/veci2/"+name+".js",UMAKE)
        for name in ("VeciRa","VeciWifiControls","VeciCron"):
            self.assertIn("globalThis."+name+"?.reset?.()",APP)

    def test_scope_permissions_no_unauthorized_write(self):
        radio=json.loads((RT/"veci2-status-acl.json").read_text())
        all_rules=json.dumps(radio)
        self.assertIn('"veci-v2-backup"',all_rules)
        for method in ("setChannel","setAccess","setAuth","survey"):
            self.assertIn('"'+method+'"',all_rules)
        v6=json.loads((V6/"files/usr/share/rpcd/acl.d/veci-v2-ipv6.json").read_text())
        rules=json.dumps(v6)
        self.assertIn('"veci.v2.ra"',rules)
        self.assertIn('"save"',rules)
        self.assertIn("check_ap",(RT/"veci2-wifi").read_text())

    def test_native_scripts_and_22ghz_single_radio_safety(self):
        for script in (RT/"veci2-wifi",RT/"veci2-cron",RT/"veci2-services",
                       V6/"files/usr/libexec/rpcd/veci2-ra",UI/"files/www/cgi-bin/veci2-backup"):
            subprocess.run(["sh","-n",str(script)],check=True,capture_output=True,timeout=10)
        controls=(RT/"veci2-wifi-controls").read_text()
        self.assertIn("2412",controls)
        self.assertIn("2484",controls)
        self.assertNotIn("5180",controls)
        self.assertIn("HTTPS", (UI/"files/www/cgi-bin/veci2-backup").read_text())

    def test_not_ready_for_final_build_even_with_source_presence(self):
        items=json.loads((ROOT/"rebuild/veci-v2/contracts/veci-v2-rebuild-contract.json").read_text())
        self.assertEqual(len(items["required_core"]),40)
        self.assertFalse(items["flash_authorized"])
        self.assertTrue(any(x["v2_state"]=="not_ported_to_v2" for x in items["required_core"]))


if __name__=="__main__":
    unittest.main()
