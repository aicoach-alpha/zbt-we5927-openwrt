"""Read-only rescue: avoid PowerShell reinterpreting grep alternation as remote commands."""
import subprocess
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"scripts/router/veci-live-wifi-readonly-triage.sh"

class WifiReadOnlyTriage(unittest.TestCase):
    def test_read_only_and_no_secret_disclosure(self):
        src=SCRIPT.read_text()
        subprocess.run(["sh","-n",str(SCRIPT)],check=True)
        for item in ("TRIAGE_ABORT=wrong_board","RADIO0_UP","RADIO0_PENDING",
                     "RADIO0_PRIMARY_IFNAME","HOSTAPD_OBJECTS","KERNEL_INTERFACES",
                     "HOSTAPD_NETIFD_ERRORS_FILTERED","KERNEL_MT76_ERRORS_FILTERED",
                     "NETIFD_PROCESS_COUNT","LAN_BRIDGE","LTE_BOUND_HTTPS=PASS_200",
                     "TRIAGE_END=OK"):
            self.assertIn(item,src)
        for dangerous in ("uci set ", "uci -q set", "uci commit ", "uci -q commit",
                          "ubus call network reload","wifi up","wifi down","wifi reload",
                          "sysupgrade","reboot","killall","procd_restart","AT+CFUN"):
            self.assertNotIn(dangerous,src)
        self.assertNotIn('p AP_KEY "',src)
        self.assertNotIn('cat /etc/config/wireless',src)
        self.assertIn("AP_KEY_PRESENT",src)
        self.assertIn("grep -Eiv 'ssid|psk|password",src)

    def test_wrong_device_refused_without_mutation(self):
        result=subprocess.run(["sh",str(SCRIPT)],text=True,capture_output=True)
        self.assertEqual(result.returncode,3)
        self.assertIn("TRIAGE_ABORT=wrong_board",result.stdout)

if __name__=="__main__":
    unittest.main()
