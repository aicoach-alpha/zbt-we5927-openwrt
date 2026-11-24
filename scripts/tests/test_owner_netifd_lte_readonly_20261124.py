"""Fail-closed read-only duplicate-netifd and LTE diagnosis."""
import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"scripts/router/veci-netifd-lte-readonly-20261124.sh"

class NetifdLteReadOnly(unittest.TestCase):
    def test_readonly_command_surface(self):
        s=SCRIPT.read_text()
        subprocess.run(["sh","-n",str(SCRIPT)],check=True)
        for required in ("TRIAGE_ABORT=WRONG_BOARD","NETIFD_PROCESS_IDENTITIES",
                         "NETIFD_PPID","NETIFD_PROCESS_COUNT",
                         "UBUS_OBJECT_HEALTH","LTE_INTERFACE_UBUS",
                         "UDHCPC_PROCESS_COUNT","NOTIFY_PROTO_PERMISSION_DENIED_COUNT",
                         "LTE_HTTP_EXIT","LTE_HTTPS_EXIT","LTE_HTTPS_CODE",
                         "TRIAGE_END=OK","--interface 'if!usb0'"):
            self.assertIn(required,s)
        forbidden=("uci set", "uci -q set", "uci commit", "ifdown", "ifup",
                   "wifi reload", "wifi up", "network reload", "network restart",
                   "kill ", "killall", "pkill", "reboot", "sysupgrade",
                   "AT+CFUN", "logread | tail", "logread | grep")
        for fragment in forbidden:
            self.assertNotIn(fragment,s,fragment)
        self.assertIn("grep -F 'Permission denied' | wc -l",s)
        self.assertNotIn("cat /etc/config/wireless",s)

    def test_incorrect_board_refused(self):
        outcome=subprocess.run(["sh",str(SCRIPT)],capture_output=True,text=True)
        self.assertEqual(outcome.returncode,3)
        self.assertIn("TRIAGE_ABORT=WRONG_BOARD",outcome.stdout)

if __name__=="__main__":
    unittest.main()
