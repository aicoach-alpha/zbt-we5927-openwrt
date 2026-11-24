"""Safety contract for one targeted LTE restart on the sole owner router."""
import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"scripts/router/veci-lte-interface-scoped-recovery-20261124.sh"

class ScopedLteRecovery(unittest.TestCase):
    def test_fail_closed_and_only_lte_restart(self):
        text=SCRIPT.read_text()
        subprocess.run(["sh","-n",str(SCRIPT)],check=True)
        for marker in ("TRIAGE_ABORT", "canonical_procd_network_pid_changed",
                       "canonical_netifd_unhealthy", "lan_ip_not_as_expected",
                       "memory_too_low", "lte_ubus_object_missing",
                       "LTE_INTERFACE_RESTART=REQUESTED",
                       "LTE_INTERFACE_RESTART=ACCEPTED",
                       "call network.interface.lte restart", "REPAIR_END=OK",
                       "REPAIR_RESULT=LTE_PUBLIC_IP_AND_DNS_OK",
                       "REPAIR_RESULT=LTE_PUBLIC_IP_STILL_FAILS_NO_GLOBAL_RESTART"):
            if marker == "TRIAGE_ABORT":
                marker="REPAIR_STOP="
            self.assertIn(marker,text)
        body="\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
        for forbidden in ("kill ", "pkill", "killall", "reboot",
                          "sysupgrade", "wifi up", "wifi down", "ip link set",
                          "ubus call network reload","network restart","network reload",
                          "ifup ", "ifdown ", "uci set","uci commit",
                          "AT+CFUN", "usb_modeswitch", "ubus call network.interface.lan"):
            self.assertNotIn(forbidden,body)
        self.assertEqual(body.count("call network.interface.lte restart"), 1)
        self.assertTrue(text.index("PRECHECK=PASS_LAN_SAFE_PROCD_VERIFIED") <
                        text.index("call network.interface.lte restart"))
        self.assertTrue(text.index("lan_disappeared_before_restart") <
                        text.index("call network.interface.lte restart"))

    def test_non_router_fails_before_changes(self):
        p=subprocess.run(["sh",str(SCRIPT)],capture_output=True,text=True,timeout=3)
        self.assertEqual(p.returncode,3)
        self.assertIn("REPAIR_STOP=wrong_board",p.stdout)
        self.assertNotIn("LTE_INTERFACE_RESTART=REQUESTED",p.stdout)

if __name__=="__main__":
    unittest.main()
