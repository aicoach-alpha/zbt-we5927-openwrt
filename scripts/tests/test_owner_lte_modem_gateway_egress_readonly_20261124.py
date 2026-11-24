"""Read-only physical WE5927 modem gateway vs Internet DNS separation."""
import subprocess
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"scripts/router/veci-lte-modem-gateway-egress-readonly-20261124.sh"

class LteGatewayReadOnly(unittest.TestCase):
    def test_no_state_mutation_and_bounded_operations(self):
        s=SCRIPT.read_text()
        subprocess.run(["sh","-n",str(SCRIPT)],check=True)
        for item in ("TRIAGE_ABORT=WRONG_BOARD","MODEM_PING_EXIT=",
                     "MODEM_HTTP_EXIT=","PUBLIC_TLS_IP_EXIT=",
                     "ip -4 route show default","ip -4 neigh show",
                     "--interface 'if!usb0'","https://1.1.1.1/",
                     "http://192.168.7.1/", "--max-time 5", "--max-time 8",
                     "TRIAGE_END=OK"):
            self.assertIn(item,s,item)
        body="\n".join(line for line in s.splitlines() if not line.lstrip().startswith("#"))
        for forbidden in ("kill ","killall","pkill","reboot","sysupgrade",
                          "wifi up","wifi down","network reload","network restart",
                          "ifup ","ifdown ","uci set","uci commit","AT+CFUN",
                          "ubus call","curl -X POST","--data"):
            self.assertNotIn(forbidden,body,forbidden)
        self.assertNotIn("cat /etc/config/network",s)
        self.assertNotIn("cat /proc/",s)
    def test_wrong_board_aborts_before_curl(self):
        p=subprocess.run(["sh",str(SCRIPT)],capture_output=True,text=True,timeout=3)
        self.assertEqual(p.returncode,3)
        self.assertIn("TRIAGE_ABORT=WRONG_BOARD",p.stdout)
        self.assertNotIn("MODEM_HTTP_EXIT",p.stdout)

if __name__=="__main__":
    unittest.main()
