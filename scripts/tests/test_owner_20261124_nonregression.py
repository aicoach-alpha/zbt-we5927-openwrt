"""Physical UAT decisions are binding, not negotiable by CI source-only PASS."""
from pathlib import Path
import json
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "rebuild/veci-v2"
WEB = BASE / "packages/veci-v2-ui/files/www/veci2"
RUNTIME = BASE / "packages/veci-v2-runtime"
NATIVE = ROOT / "source/we5927-lte/src/we5927-at.c"


class OwnerUatNonRegression(unittest.TestCase):
    def test_no_ussd_production_surface_or_rpc_acl(self):
        self.assertFalse((WEB/"ussd.js").exists())
        self.assertFalse((RUNTIME/"veci2-ussd").exists())
        for p in [WEB/"index.html",WEB/"app.js",WEB/"sms-center.js",
                  RUNTIME/"Makefile",RUNTIME/"veci2-status-acl.json",
                  BASE/"packages/veci-v2-ui/Makefile"]:
            self.assertNotIn("ussd",p.read_text().lower(),str(p))
        acl = json.loads((RUNTIME/"veci2-status-acl.json").read_text())
        self.assertNotIn("ussd",json.dumps(acl).lower())

    def test_ussd_removed_from_active_release_contract(self):
        config=json.loads((BASE/"contracts/veci-v2-rebuild-contract.json").read_text())
        self.assertEqual(len(config["required_core"]),39)
        self.assertNotIn("lte_ussd",[r["id"] for r in config["required_core"]])
        owner=json.loads((BASE/"contracts/owner-hardware-uat-20261124.json").read_text())
        self.assertEqual(owner["owner_decisions"]["ussd"]["decision"],"PERMANENTLY_RETIRED")
        evidence=json.loads((BASE/"contracts/owner-final-source-evidence.json").read_text())
        self.assertNotIn("lte_ussd",evidence["modules"])

    def test_native_at_transport_has_no_ussd_mode_and_refuses_cusd(self):
        source=NATIVE.read_text()
        self.assertNotIn("--ussd-stdin",source)
        self.assertIn('!strncasecmp(cmd,"AT+CUSD",7)',source)
        self.assertNotIn("AT+CUSD=1",source)
        with tempfile.TemporaryDirectory() as directory:
            exe=Path(directory)/"test-at"
            subprocess.run(["gcc","-O2","-Wall","-Wextra","-Werror",
                            str(NATIVE),"-o",str(exe)],check=True,capture_output=True)
            for command in ["AT+CUSD=1", "at+cusd=2", "--retired-mode"]:
                result=subprocess.run([str(exe),"/dev/no_such_modem",command,"1000"],
                                      capture_output=True,timeout=5)
                self.assertEqual(result.returncode,2,command)

    def test_retirement_is_enforced_in_future_build_and_acceptance(self):
        accepted=(ROOT/"scripts/accept_owner_lte_sources.py").read_text()
        workflow=(ROOT/".github/workflows/veci-v2-lab-image.yml").read_text()
        checks=(ROOT/".github/workflows/veci-v2-rebuild-source.yml").read_text()
        self.assertNotIn('"lte_ussd":{',accepted)
        self.assertNotIn("veci2-ussd",accepted)
        self.assertIn("usr/libexec/rpcd/veci.v2.ussd",workflow)
        self.assertIn("www/veci2/ussd.js",workflow)
        self.assertIn("RETIRED_USSD_UI_RESURRECTED",workflow)
        self.assertIn("RETIRED_USSD_ACL_RESURRECTED",workflow)
        self.assertIn("assert x['required_modules'] == 39",checks)

    def test_professional_navigation_and_real_data_contract(self):
        html=(WEB/"index.html").read_text()
        tabs=re.findall(r'<button class="tab(?: active)?" type="button" data-page="([^"]+)"',html)
        self.assertEqual(tabs,["overview","network","sms","settings"])
        self.assertIn('data-scope="network"',html)
        self.assertIn('data-scope="settings"',html)
        self.assertIn('id="traffic-chart"',html)
        self.assertIn('id="sms-diagnostics"',html)
        app=(WEB/"app.js").read_text()
        self.assertIn("sampleTraffic",app)
        self.assertIn("verifyInternetLive",app)
        self.assertIn("setSubgroup",app)
        provider=(RUNTIME/"veci2-status").read_text()
        for name in ["call:traffic","call:internetCheck","call:smsDiagnostics"]:
            self.assertIn(name,provider)
        self.assertIn("/sys/class/net/$1/statistics/$2",provider)
        self.assertIn("if!usb0",provider)
        self.assertIn('"hardware_sms_verified":false',provider)

if __name__=="__main__":
    unittest.main()
