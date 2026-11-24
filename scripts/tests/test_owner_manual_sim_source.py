import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime/veci2-sim-manual"
SOURCE=SCRIPT.read_text()

class ManualSimReview(unittest.TestCase):
    def test_syntax(self):
        r=subprocess.run(["sh","-n",str(SCRIPT)],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)

    def test_rpc_schema_no_device_access(self):
        p=subprocess.run(["sh",str(SCRIPT),"list"],capture_output=True,text=True,timeout=5)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn('"switchSim"',p.stdout)
        self.assertIn('"confirmation"',p.stdout)

    def test_untrusted_methods_fail(self):
        p=subprocess.run(["sh",str(SCRIPT),"call","arbitrary"],capture_output=True,text=True,timeout=5)
        self.assertEqual(p.returncode,0)
        self.assertIn('"unsupported_method"',p.stdout)

    def test_manual_preconditions(self):
        for literal in [
            "zbtlink,zbt-we5927","wrong_sim_selector","unexpected_sim1_polarity",
            "unexpected_sim2_polarity","wrong_modem_identity","pending_lte_changes",
            "selector_unreadable","disable_auto_failover_first","explicit_confirmation_required",
            "flock -n 9",'/usr/sbin/we5927-lte sim "$slot"',
            'reconnect_failed_rollback_attempted', "selector_not_confirmed"
        ]:
            self.assertIn(literal,SOURCE)
        self.assertNotIn("AT+CFUN",SOURCE)
        self.assertNotIn("gpio_set",SOURCE)

    def test_no_implicit_switch(self):
        self.assertIn('if [ "$2" = switchSim ]; then',SOURCE)
        self.assertIn("1:SWITCH_SIM_1|2:SWITCH_SIM_2",SOURCE)

if __name__=="__main__":
    unittest.main()
