"""Source provenance, script syntax and runtime wiring; not hardware PASS."""
import hashlib,json,subprocess,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
NAME='ussd'
REV='331ebf7'
SUFFIX='ussd'
RT=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime"
UI=ROOT/"rebuild/veci-v2/packages/veci-v2-ui"
class ExistingModuleIntegration(unittest.TestCase):
 def test_reuse_original_source(self):
  for rel in ("rebuild/veci-v2/packages/veci-v2-runtime/veci2-"+SUFFIX,
              "rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2/"+SUFFIX+".js"):
   expected=subprocess.check_output(["git","-C",str(ROOT),"show",REV+":"+rel])
   self.assertEqual((ROOT/rel).read_bytes(),expected)
 def test_native_source_integrated(self):
  script=RT/("veci2-"+SUFFIX)
  subprocess.run(["sh","-n",str(script)],check=True)
  self.assertIn("zbtlink,zbt-we5927",script.read_text())
  js=UI/"files/www/veci2"/(SUFFIX+".js")
  subprocess.run(["node","--check",str(js)],check=True)
  self.assertIn(SUFFIX+".js",(UI/"Makefile").read_text())
  self.assertIn("veci2-"+SUFFIX,(RT/"Makefile").read_text())
  acl=json.loads((RT/"veci2-status-acl.json").read_text())
  self.assertIn("veci.v2."+("simlock" if NAME=="pin" else "ussd"),str(acl))
 def test_private_at_transport(self):
  at=(ROOT/"source/we5927-lte/src/we5927-at.c").read_text()
  self.assertIn("--sim-pin-stdin",at)
  self.assertIn("--sim-puk-stdin",at)
  self.assertIn("--ussd-stdin",at)
  self.assertIn("private_cmd",at)
  self.assertIn("ussd",at)
 def test_not_hardware_pass(self):
  contract=json.loads((ROOT/"rebuild/veci-v2/contracts/veci-v2-rebuild-contract.json").read_text())
  self.assertFalse(contract["flash_authorized"])
  module=next(x for x in contract["required_core"] if x["id"]==("lte_apn_pin_puk" if NAME=="pin" else "lte_ussd"))
  self.assertIn(module["v2_state"], ("not_ported_to_v2", "source_verified"))
  self.assertEqual(module["physical_uat"], "not_run")
