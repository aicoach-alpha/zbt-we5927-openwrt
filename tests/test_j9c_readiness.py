"""J9C fail-closed static readiness checks, never touches a router."""
import importlib.util
import sys
import unittest
from pathlib import Path
p=Path(__file__).resolve().parents[1]/"scripts/j9c_readiness_audit.py"
spec=importlib.util.spec_from_file_location("j9c",p)
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)
def fixtures():
    return {
      "guest":"enable_portal() {\n provision_base || return 1\n wifi reload || return 1\n}\n",
      "voucher":"method_status() {\n cleanup_expired\n}\n",
      "wireguard":"method_create() {\n uci set network.peer.route_allowed_ips=1\n}\n",
      "core":'''method_firmware_apply() {
 [ "$token" = "$validation_token" ]
}
method_firmware_validate() {
 signature_state=signed
}
method_app_action() {
 if [ -n "$cleanup" ]; then
   check
 fi
}
'''
    }
class J9CReadiness(unittest.TestCase):
    def test_all_known_risks_blocked(self):
        f=m.findings(fixtures())
        self.assertEqual(len(f),5)
        self.assertTrue(all(x=="BLOCKED" for x in f.values()),f)
    def test_status_purity_cannot_auto_pass(self):
        src=fixtures();src["voucher"]="method_status() {\n json_dump\n}\n"
        self.assertEqual(m.findings(src)["voucher_read_side_effect"],"REVIEW_REQUIRED")
    def test_route_change_cannot_auto_pass(self):
        src=fixtures();src["wireguard"]="method_create() {\n return 0\n}\n"
        self.assertEqual(m.findings(src)["wireguard_peer_auto_routes"],"REVIEW_REQUIRED")
    def test_cleanup_guard_cannot_auto_pass(self):
        src=fixtures();src["core"]=src["core"].replace('if [ -n "$cleanup" ]; then','if [ "$cleanup_ok" = true ]; then')
        self.assertEqual(m.findings(src)["app_cleanup_empty_response"],"REVIEW_REQUIRED")
    def test_missing_function_fails(self):
        with self.assertRaises(ValueError):m.method("some() {\n}\n","missing")
    def test_functions_are_separate(self):
        t="one() {\n echo yes\n}\ntwo() {\n echo no\n}\n"
        self.assertNotIn("no",m.method(t,"one"))
    def test_no_release_authorization(self):
        source=p.read_text()
        self.assertIn('"flash_decision":"NO_GO"',source)
        self.assertIn('"product_readiness":"BLOCKED"',source)
        self.assertIn('"NOT_TESTED" for g in GATES',source)
