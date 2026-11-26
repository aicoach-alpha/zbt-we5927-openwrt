#!/usr/bin/env python3
"""A modem's explicit CME SIM-absent response must never be labeled AT-busy."""
from pathlib import Path
import subprocess,unittest
ROOT=Path(__file__).resolve().parents[2]
L=ROOT/"source/we5927-lte/files/usr/sbin/we5927-lte"
M=ROOT/"files/usr/sbin/we5927-lte"
class SimAbsent(unittest.TestCase):
 def test_classify_absent_sim_without_data_or_gpio_mutation(self):
  s=L.read_text()
  self.assertEqual(s,M.read_text())
  start=s.index("modem_readiness_phase() {")
  end=s.index("radio_or_link_lost() {",start)
  fragment=s[start:end]
  self.assertIn("*'+CME ERROR: SIM not inserted'*) echo sim_missing",fragment)
  self.assertIn("*) echo at_busy_or_unavailable",fragment)
  self.assertNotIn("gpio_set",fragment)
  self.assertNotIn("AT+CFUN",fragment)
  subprocess.run(["sh","-n",str(L)],check=True)
if __name__=="__main__":unittest.main()
