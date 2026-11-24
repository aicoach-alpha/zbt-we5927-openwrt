"""Safety and presence gates for physical modem-only diagnosis."""
import subprocess
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"scripts/router/veci-lte-usb-link-readonly-20261124.sh"
class LteUsbLinkReadOnly(unittest.TestCase):
    def test_exact_board_and_nonmutating(self):
        text=SCRIPT.read_text()
        subprocess.run(["sh","-n",str(SCRIPT)],check=True)
        for item in ("TRIAGE_ABORT=WRONG_BOARD", "USB0_PRESENT=yes",
                     "QUALCOMM_05C6_902E_PRESENT", "USB0_IPV4=assigned",
                     "LTE_ROUTE=present", "LTE_UBUS=unavailable",
                     "UDHCPC_COUNT=", "MEM_AVAILABLE_KIB=", "TRIAGE_END=OK"):
            self.assertIn(item,text)
        content="\n".join(line for line in text.splitlines() if not line.strip().startswith("#"))
        for forbidden in ("kill ", "killall", "pkill", "restart", "reload", "ifup ",
                          "ifdown ", "uci set", "uci commit", "reboot",
                          "sysupgrade", "wifi up", "wifi down", "AT+CFUN",
                          "echo > /sys/", "ubus call service set"):
            self.assertNotIn(forbidden,content)
    def test_refuse_unexpected_board(self):
        r=subprocess.run(["sh",str(SCRIPT)],capture_output=True,text=True,timeout=3)
        self.assertEqual(r.returncode,3)
        self.assertIn("TRIAGE_ABORT=WRONG_BOARD",r.stdout)
        self.assertNotIn("QUALCOMM_05C6_902E_PRESENT",r.stdout)
if __name__=="__main__":
    unittest.main()
