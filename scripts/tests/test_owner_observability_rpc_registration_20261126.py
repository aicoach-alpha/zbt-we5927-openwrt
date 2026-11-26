#!/usr/bin/env python3
"""Ensure rpcd can enumerate health provider with only the list argument."""
from pathlib import Path
import json,subprocess,unittest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime/veci2-observe-rpc"
class RpcRegistration(unittest.TestCase):
 def test_list_one_argument_no_unbound_positionals(self):
  for args in (["list"],["list",""]):
   proc=subprocess.run(["busybox","ash",str(SCRIPT),*args],capture_output=True,text=True,timeout=3)
   self.assertEqual(proc.returncode,0,proc.stderr)
   self.assertEqual(json.loads(proc.stdout),{"status":{}})
 def test_read_only_contract_and_no_network_mutation(self):
  source=SCRIPT.read_text()
  self.assertIn('case "${1:-}:${2:-}"',source)
  self.assertIn('exec timeout 3 /usr/libexec/veci2-observe status',source)
  for token in ('ifup ', 'ifdown ', 'wifi up', 'wifi reload', 'reboot','AT+CFUN'):
   self.assertNotIn(token,source)
if __name__=="__main__":unittest.main()
