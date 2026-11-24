"""Safeguards for minimal low-RAM owner diagnostics."""
import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"scripts/router/veci-netifd-wchan-memory-readonly-20261124.sh"

class WchanMemoryReadOnly(unittest.TestCase):
    def test_script_syntax_and_no_mutations(self):
        script=SCRIPT.read_text()
        subprocess.run(["sh","-n",str(SCRIPT)],check=True)
        for marker in ("TRIAGE_ABORT=wrong_board", "VECI_NETIFD_WCHAN_MEMORY_20261124",
                       "/proc/$pid/wchan", "MemAvailable:", "memory allocation failure",
                       "LTE_CONTROL_STATE", "UBUS", "UDHCPC_COUNT", "TRIAGE_END=OK"):
            if marker=="UBUS":
                marker="ubus -S -t 2"
            self.assertIn(marker,script)
        body="\n".join(line for line in script.splitlines() if not line.lstrip().startswith("#"))
        for op in ("kill ", "pkill", "killall", "service restart", "network reload",
                   "network restart", "ifup ", "ifdown ", "wifi up", "wifi down",
                   "sysupgrade", "reboot", "uci set", "uci commit", "AT+CFUN"):
            self.assertNotIn(op,body,op)
        self.assertNotIn("cat /proc/$pid/cmdline",body)
        self.assertNotIn("/etc/config/network",body)

    def test_refuses_other_board(self):
        t=subprocess.run(["sh",str(SCRIPT)],capture_output=True,text=True,timeout=3)
        self.assertEqual(t.returncode,3)
        self.assertIn("TRIAGE_ABORT=wrong_board",t.stdout)

if __name__=="__main__":
    unittest.main()
