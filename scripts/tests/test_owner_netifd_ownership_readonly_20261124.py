"""Read-only proof-of-ownership gate for duplicate netifd diagnosis."""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/router/veci-netifd-ownership-readonly-20261124.sh"

class NetifdOwnershipReadOnly(unittest.TestCase):
    def test_script_safe_and_syntactically_valid(self):
        s = SCRIPT.read_text()
        subprocess.run(["sh", "-n", str(SCRIPT)], check=True)
        for item in ("WRONG_BOARD", "PROCD_NETWORK_PID",
                     "NETIFD_CANDIDATE", "PROC_PARENT", "PROC_EXE",
                     "USB0_IPV4", "USB0_DEFAULT_ROUTE", "TRIAGE_END=OK"):
            self.assertIn(item, s)
        for dangerous in ("killall", "pkill", "kill -", "uci set", "uci commit",
                          "wifi reload", "wifi up", "wifi down", "network reload",
                          "network restart", "reboot", "sysupgrade",
                          "ifup ", "ifdown ", "AT+CFUN", "ubus call service set"):
            self.assertNotIn(dangerous, s)
        self.assertIn("call service list", s)
        self.assertIn("read_proc", s)
        self.assertNotIn("cat /proc/$pid/cmdline", s)
        self.assertNotIn("cat /etc/config/network", s)

    def test_wrong_board_fails_closed(self):
        test = subprocess.run(["sh", str(SCRIPT)], capture_output=True,
                              text=True, timeout=3)
        self.assertEqual(test.returncode, 3)
        self.assertIn("TRIAGE_ABORT=WRONG_BOARD", test.stdout)

if __name__ == "__main__":
    unittest.main()
