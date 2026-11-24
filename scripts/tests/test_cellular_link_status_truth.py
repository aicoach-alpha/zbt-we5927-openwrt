"""Protect cellular link vs router Internet verification semantics."""
from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
FRONT=(ROOT/"source/veci-core/veci/js/pages/cellular.js").read_text()
HOME=(ROOT/"source/veci-core/veci/js/pages/home.js").read_text()
RPCD=(ROOT/"source/veci-core/files/rpcd-veci").read_text()
PROVIDER=(ROOT/"source/veci-cellular-we5927/files/usr/libexec/rpcd/veci.cellular").read_text()
LTE=(ROOT/"source/we5927-lte/files/usr/sbin/we5927-lte").read_text()
SH=shutil.which("sh") or "/bin/sh"

def function(name):
    start=RPCD.index(name+"() {")
    tail=RPCD[start:]
    return tail.split("\n}\n",1)[0]+"\n}\n"

class LinkVsInternet(unittest.TestCase):
    def test_provider_exposes_independent_link_and_verification(self):
        self.assertIn('json_get_var data_link_up data_link_up',PROVIDER)
        self.assertIn('json_add_boolean data_link_up 1',PROVIDER)
        self.assertIn('json_add_boolean data_link_up 0',PROVIDER)
        self.assertIn('json_add_boolean internet_verified 1',PROVIDER)
        self.assertIn('json_add_boolean internet_verified 0',PROVIDER)
        self.assertIn('json_add_boolean data_link_up "$data_link"',LTE)
        self.assertIn('json_add_boolean internet_verified "$online"',LTE)

    def test_frontend_does_not_confuse_stale_watchdog_with_link(self):
        self.assertIn('const dataLinkActive =',FRONT)
        self.assertIn('status.data_link_up === true',FRONT)
        self.assertIn('Boolean(status.ipv4 && status.gateway)',FRONT)
        self.assertIn("badge(dataLinkActive ? 'LTE data link active'", FRONT)
        self.assertNotIn("online ? 'Data link active'",FRONT)
        self.assertIn("if (dataLinkActive)",FRONT)
        self.assertIn("api.veci('internetStatus', {}, { timeout: 6500 })",FRONT)
        self.assertIn("'Reachable (router)'",FRONT)
        self.assertIn("'Not verified'",FRONT)
        self.assertIn("'No LTE data route'",FRONT)
        self.assertNotIn("if (online)",FRONT)
        self.assertIn("api.veci('internetStatus', {}, { timeout: 6500 })",HOME)

    def shell_internet(self,success):
        with tempfile.TemporaryDirectory() as t:
            code=function("method_internet_status")
            code=code.replace('cache=/tmp/veci-internet-status',f"cache={t}/status")
            script=("ping() { return "+("0" if success else "1")+"; }\n"
                    +code+"\nmethod_internet_status\nmethod_internet_status\n")
            out=subprocess.run([SH,"-c",script],capture_output=True,text=True,timeout=5,check=True)
            return [json.loads(line) for line in out.stdout.splitlines()]

    def test_failed_single_target_coverage_is_unverified_not_proven_offline(self):
        first,second=self.shell_internet(False)
        self.assertEqual(first["status"],"unknown")
        self.assertIsNone(first["reachable"])
        self.assertFalse(first["cached"])
        self.assertEqual(second["status"],"unknown")
        self.assertTrue(second["cached"])

    def test_successful_probe_is_reachable_and_cached(self):
        first,second=self.shell_internet(True)
        self.assertEqual(first["status"],"reachable")
        self.assertTrue(first["reachable"])
        self.assertFalse(first["cached"])
        self.assertEqual(second["status"],"reachable")
        self.assertTrue(second["cached"])

    def test_probe_timeout_bounds_are_not_less_than_field_test(self):
        self.assertIn('ping -c 1 -W 2 "$target"',RPCD)
        self.assertNotIn('ping -c 1 -W 1 "$target"',function("method_internet_status"))

if __name__ == "__main__":
    unittest.main()
