"""Source safety contract: only LTE ubus down/up after exact-board and LAN guards."""
import subprocess
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"scripts/router/veci-lte-scoped-down-up-recovery-20261124.sh"

class LteScopedDownUp(unittest.TestCase):
    def test_lte_only_single_cycle_source_contract(self):
        s=SCRIPT.read_text()
        subprocess.run(["sh","-n",str(SCRIPT)],check=True)
        for required in (
            "LTE_REPAIR_STOP=wrong_board", "lan_address_changed",
            "procd_network_owner_changed", "canonical_netifd_blocked",
            "low_memory", "lte_ubus_missing",
            "REPAIR_SKIPPED=EXTERNAL_IP_AND_DNS_ALREADY_PASS",
            "ACTION=LTE_ONLY_DOWN_UP_ONCE",
            "call network.interface.lte down '{}'",
            "call network.interface.lte up '{}'",
            "LTE_DOWN_EXIT=", "LTE_UP_EXIT=",
            "sleep 5", "LAN=192.168.1.1_PRESENT",
            "PUBLIC_IP_HTTPS_EXIT=","PUBLIC_DNS_HTTPS_EXIT=",
            "REPAIR_END=ONE_LTE_DOWN_UP_ATTEMPT_COMPLETE"):
            if required=="LTE_REPAIR_STOP=wrong_board":
                required="echo \"LTE_REPAIR_STOP=$1\""
            self.assertIn(required,s,required)
        b="\n".join(l for l in s.splitlines() if not l.lstrip().startswith("#"))
        self.assertEqual(b.count("call network.interface.lte down '{}'"),1)
        self.assertEqual(b.count("call network.interface.lte up '{}'"),1)
        self.assertLess(b.index("LAN=192.168.1.1_PRESENT"),b.index("PUBLIC_IP_HTTPS_EXIT="))
        self.assertLess(b.index("call network.interface.lte down '{}'"),b.index("call network.interface.lte up '{}'"))
        for dangerous in (
            "kill ", "killall", "pkill", "sysupgrade", "reboot", "network reload",
            "network restart", "ifup ", "ifdown ", "wifi up", "wifi down",
            "uci set","uci commit","ip link set","AT+CFUN", "usb_modeswitch",
            "call network.interface.lan down", "call network.interface.lan up"):
            self.assertNotIn(dangerous,b,dangerous)
    def test_wrong_board_does_not_mutate(self):
        r=subprocess.run(["sh",str(SCRIPT)],capture_output=True,text=True,timeout=3)
        self.assertEqual(r.returncode,3)
        self.assertIn("LTE_REPAIR_STOP=wrong_board",r.stdout)
        self.assertNotIn("ACTION=LTE_ONLY_DOWN_UP_ONCE",r.stdout)
if __name__=="__main__":
    unittest.main()
