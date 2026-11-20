import subprocess
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
FILE=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime/veci2-firewall"
SOURCE=FILE.read_text()
class FirewallOwnerSource(unittest.TestCase):
    def test_syntax(self):
        p=subprocess.run(["sh","-n",str(FILE)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
    def test_method_schema(self):
        p=subprocess.run(["sh",str(FILE),"list"],capture_output=True,text=True,timeout=5)
        self.assertEqual(p.returncode,0)
        self.assertIn('"setDmz"',p.stdout)
        self.assertIn('"addForward"',p.stdout)
    def test_denies_other_methods(self):
        p=subprocess.run(["sh",str(FILE),"call","arbitrary"],capture_output=True,text=True,timeout=5)
        self.assertIn('unsupported_method',p.stdout)
    def test_wan_policy_and_rollback(self):
        for x in ("unsafe_wan_policy", "pending_firewall_changes", "flock -n 9",
                  "invalid_lan_destination", "refuse_router_management_port",
                  "FORWARD_", "ENABLE_DMZ_", "DISABLE_DMZ", "not_owner_redirect",
                  'cp "$tmp/previous" /etc/config/firewall', "/etc/init.d/firewall reload"):
            self.assertIn(x,SOURCE)
    def test_never_loosens_wan_policy(self):
        self.assertNotIn("firewall.@zone[1].input=ACCEPT",SOURCE)
        self.assertNotIn("firewall.@defaults[0].forward=ACCEPT",SOURCE)
        self.assertNotIn("iptables -P",SOURCE)
if __name__=="__main__":
    unittest.main()
