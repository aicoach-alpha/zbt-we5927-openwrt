"""One-device, exact-PID mitigation must preserve the procd network owner."""
import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"scripts/router/veci-netifd-orphan-guarded-mitigation-20261124.sh"

class OrphanNetifdGuard(unittest.TestCase):
    def test_static_safety_contract(self):
        s=SCRIPT.read_text()
        subprocess.run(["sh","-n",str(SCRIPT)],check=True)
        for item in ("canonical=1366","orphan=16862","orphan_parent=16854",
                     "requires_explicit_apply_argument",
                     "call service list","PROCD_NETWORK_PID","orphan_pid_reused",
                     "canonical_netifd_identity_changed","orphan_parent_identity_changed",
                     "unexpected_netifd_count",
                     "lte_ipv4_already_assigned_do_not_touch",
                     "lte_route_already_present_do_not_touch",
                     "procd_owner_changed_before_signal",
                     "canonical_changed_before_signal",
                     "orphan_changed_before_signal",
                     "parent_changed_before_signal",
                     'kill -TERM "$orphan"',
                     "ORPHAN_TERM=STILL_RUNNING_NO_ESCALATION",
                     "CANONICAL_NETIFD=STILL_ALIVE",
                     "LAN_BRIDGE=STILL_PRESENT",
                     "MITIGATION_END=CANONICAL_NETWORK_PRESERVED_NO_LTE_RENEW_ATTEMPTED"):
            self.assertIn(item,s,item)
        executable="\n".join(line for line in s.splitlines() if not line.lstrip().startswith("#"))
        for forbidden in ("killall","pkill", "kill -9", "kill -KILL",
                          'kill -TERM "$canonical"', 'kill -TERM "$orphan_parent"',
                          "network reload","network restart",
                          "ifup lte","ifdown lte","wifi up","wifi down","sysupgrade",
                          "AT+CFUN","uci -q set","uci commit","reboot"):
            self.assertNotIn(forbidden,executable,forbidden)
        self.assertLess(s.index("PRECHECK=PASS_IDENTITIES_MATCH_ONLY_ORPHAN_TARGETED"),
                        s.index('kill -TERM "$orphan"'))
        self.assertLess(s.index("orphan_pid_reused"),
                        s.index('kill -TERM "$orphan"'))
        self.assertIn('[ "$owner" = "$canonical" ]',s)

    def test_wrong_device_no_process_mutation(self):
        t=subprocess.run(["sh",str(SCRIPT),"--apply"],capture_output=True,text=True,timeout=3)
        self.assertEqual(t.returncode,3)
        self.assertIn("MITIGATION_STOP=wrong_board",t.stdout)
        self.assertNotIn("ORPHAN_TERM=REQUESTED",t.stdout)

if __name__=="__main__":
    unittest.main()
