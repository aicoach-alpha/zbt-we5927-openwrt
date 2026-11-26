#!/usr/bin/env python3
"""SIM manual CLI failure must preserve original return code and roll back safely."""
from pathlib import Path
import subprocess, unittest
root=Path(__file__).resolve().parents[2]
source=(root/"source/we5927-lte/files/usr/sbin/we5927-lte").read_text()
base,dispatch=source.rsplit('\ncase "$1" in',1)
class Rollback(unittest.TestCase):
 def test_manual_sim2_apn_failure_restores_sim1(self):
  overrides="""slot=1
cfg() { [ "$1" = sim ] && printf '%s\\n' "$slot"; }
selector_slot() { echo "$slot"; }
set_sim() { slot=$1; echo "set $1"; }
start_selected_sim() { echo "start $1:$slot"; [ "$slot" = 1 ]; }
log() { echo "LOG:$*" >&2; }
"""
  p=subprocess.run(["sh","-c",base+"\n"+overrides+'\ncase "$1" in'+dispatch,'script','sim','2'],
                   text=True,capture_output=True,timeout=4)
  self.assertNotEqual(p.returncode,0)
  self.assertEqual(p.stdout.splitlines(),["set 2","start require_ready:2","set 1","start restore:1"])
  self.assertIn("rollback confirmed to SIM1",p.stderr)
 def test_same_slot_never_power_cycles_or_reconnects(self):
  overrides="""cfg() { [ "$1" = sim ] && echo 1; }
selector_slot() { echo 1; }
set_sim() { echo ILLEGAL_SIM_MOVE; }
start_selected_sim() { echo ILLEGAL_MODEM_CYCLE; }
log() { echo "$*" >&2; }
"""
  p=subprocess.run(["sh","-c",base+"\n"+overrides+'\ncase "$1" in'+dispatch,'script','sim','1'],
                   capture_output=True,text=True,timeout=4)
  self.assertEqual(p.returncode,0,p.stderr)
  self.assertEqual(p.stdout,"")
  self.assertIn("LTE left untouched",p.stderr)
 def test_selector_mismatch_refuses_before_gpio_move(self):
  overrides="""cfg() { echo 1; }
selector_slot() { echo 2; }
set_sim() { echo FORBIDDEN; }
log() { :; }
"""
  p=subprocess.run(["sh","-c",base+"\n"+overrides+'\ncase "$1" in'+dispatch,'script','sim','2'],
                   text=True,capture_output=True,timeout=4)
  self.assertEqual(p.returncode,3)
  self.assertNotIn("FORBIDDEN",p.stdout)
if __name__=="__main__":unittest.main()
