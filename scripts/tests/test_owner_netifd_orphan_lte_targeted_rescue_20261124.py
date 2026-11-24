"""Exact PID only orphan-removal and LTE-only retry, tested without device mutation."""
import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"scripts/router/veci-netifd-orphan-lte-targeted-rescue-20261124.sh"

class OrphanLteRecoverySafety(unittest.TestCase):
    def test_expected_process_and_no_global_network_actions(self):
        s=SCRIPT.read_text()
        subprocess.run(["sh","-n",str(SCRIPT)],check=True)
        markers=[
            "explicit_apply_required", "procd_network_owner_changed",
            "procd_netifd_identity_wrong", "procd_netifd_not_healthy",
            "memory_below_12mib", "lte_ubus_missing_before_term", "extra_netifd_identity_changed",
            "extra_netifd_parent_changed", "unexpected_netifd_count",
            "usb0_ipv4_recovered_avoid_kill",
            "usb0_route_recovered_avoid_kill", "extra_pid_reused",
            "canonical_not_sleeping_before_signal",
            "extra_changed_before_signal", "parent_changed_before_signal",
            "usb0_ipv4_reappeared_before_signal",
            "usb0_route_reappeared_before_signal",
            "memory_dropped_before_signal",
            "ACTION=TERM_ONLY_NONPROCD_NETIFD_16862",
            "kill -TERM 16862",
            "ORPHAN_TERM=STILL_RUNNING_NO_ESCALATION",
            "ORPHAN_TERM=ENDED_OR_ZOMBIE",
            "canonical_owner_lost_after_term", "canonical_unhealthy_after_term", "lte_ubus_lost_after_term",
            "wired_lan_lost_after_term",
            "RESCUE_RESULT=EXTERNAL_EGRESS_RECOVERED_NO_LTE_CYCLE_NEEDED",
            "ACTION=ONE_LTE_ONLY_DOWN_UP_AFTER_ORPHAN_TERM",
            "call network.interface.lte down '{}'",
            "call network.interface.lte up '{}'",
            "PUBLIC_IP_HTTPS_EXIT=",
            "PUBLIC_DNS_HTTPS_EXIT=",
            "RESCUE_END=COMPLETE_NO_FURTHER_MUTATION",
        ]
        for marker in markers:
            self.assertIn(marker,s,marker)
        body="\n".join(x for x in s.splitlines() if not x.lstrip().startswith("#"))
        for dangerous in (
            "killall", "pkill", "kill -9", "kill -KILL",
            "kill -TERM 1366", "kill -TERM 16854",
            "reboot", "sysupgrade", "wifi up", "wifi down",
            "network reload", "network restart", "ifup ", "ifdown ",
            "uci set", "uci commit", "ip link set", "AT+CFUN",
            "usb_modeswitch", "call network.interface.lan",
        ):
            self.assertNotIn(dangerous,body,dangerous)
        self.assertEqual(body.count("kill -TERM 16862"),1)
        self.assertEqual(body.count("call network.interface.lte down '{}'"),1)
        self.assertEqual(body.count("call network.interface.lte up '{}'"),1)
        self.assertLess(s.index("extra_pid_reused"),s.index("kill -TERM 16862"))
        self.assertLess(s.index("usb0_ipv4_reappeared_before_signal"),s.index("kill -TERM 16862"))
        self.assertLess(s.index("kill -TERM 16862"),s.index("call network.interface.lte down '{}'"))
        self.assertLess(s.index("call network.interface.lte down '{}'"),s.index("call network.interface.lte up '{}'"))

    def test_wrong_board_fails_before_signal(self):
        r=subprocess.run(["sh",str(SCRIPT),"--apply"],capture_output=True,text=True,timeout=3)
        self.assertEqual(r.returncode,3)
        self.assertIn("RESCUE_STOP=wrong_board",r.stdout)
        self.assertNotIn("ACTION=TERM_ONLY_NONPROCD_NETIFD_16862",r.stdout)

    def test_no_argument_cannot_apply(self):
        # Need a mocked board to reach the argument guard; a static ordering gate
        # catches accidental argument bypasses in addition to the wrong-board run.
        s=SCRIPT.read_text()
        self.assertLess(s.index("explicit_apply_required"),s.index("kill -TERM 16862"))

if __name__=="__main__":
    unittest.main()
