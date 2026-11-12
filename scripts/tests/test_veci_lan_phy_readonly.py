import re
import subprocess
import unittest
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/"veci-lan-phy-readonly.sh"

class TestMT7628LanReadOnly(unittest.TestCase):
    def test_shell_syntax(self):
        subprocess.run(["sh","-n",str(SCRIPT)],check=True)

    def test_no_disruptive_commands(self):
        src=SCRIPT.read_text()
        actual="\n".join(line for line in src.splitlines()
                         if line.strip() and not line.lstrip().startswith("#"))
        forbidden=[
            r"\buci\s+(?:set|delete|add|commit)\b",
            r"\bswconfig\s+dev\s+\S+\s+(?:set|apply|load|reset)\b",
            r"\b(?:ifup|ifdown|reboot|sysupgrade|mtd)\b",
            r"\bwifi\s+(?:reload|up|down)\b",
            r"\/etc\/init\.d\/(?:network|firewall|dnsmasq|we5927-lte)\b",
            r"\/sys\/class\/gpio\/",
        ]
        for pattern in forbidden:
            self.assertNotRegex(actual,pattern)

    def test_read_only_switch_link_format(self):
        cmd=(r"sed -n 's/.*port:\([0-9][0-9]*\) "
             r"link:\(up\|down\).*/switch_port_\1_link=\2/p'")
        sample=("Port 0:\n  link: port:0 link:down\n"
                "Port 1:\n  link: port:1 link:up speed:100baseT full-duplex\n"
                "Port 6:\n  link: port:6 link:up speed:1000baseT\n")
        result=subprocess.run(["sh","-c",cmd],input=sample,
                              text=True,capture_output=True,check=True)
        self.assertEqual(result.stdout.strip().splitlines(),
                         ["switch_port_0_link=down","switch_port_1_link=up",
                          "switch_port_6_link=up"])

    def test_does_not_collect_secrets(self):
        src=SCRIPT.read_text()
        self.assertNotIn("network.wireless",src)
        self.assertNotIn("password",src.lower())
        for sensitive in ("imei", "imsi", "iccid", "macaddr", "apn", "ssid", "nvram"):
            self.assertNotIn(sensitive,src.lower().replace("macaddr_factory", ""))

    def test_phy_truth_not_cpu_eth0(self):
        src=SCRIPT.read_text()
        self.assertIn("swconfig dev switch0 show",src)
        self.assertIn("CPU-facing switch",src)
        self.assertIn("network.interface.lan status",src)

if __name__=="__main__":
    unittest.main()
