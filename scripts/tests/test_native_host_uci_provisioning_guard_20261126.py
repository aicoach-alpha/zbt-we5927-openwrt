"""Native host fixtures can run before source receipts are renewed; firmware gates stay closed."""
from pathlib import Path
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[2]
PROVISION=ROOT/"scripts/ci/provision-native-uci-tests.sh"
SOURCE=ROOT/"rebuild/veci-v2/ci/source-completion-gate.py"
WORKFLOW=ROOT/".github/workflows/veci-v2-rebuild-source.yml"
class NativeFixtureGuard(unittest.TestCase):
 def test_tool_provision_only_no_firmware_or_flash(self):
  s=PROVISION.read_text()
  self.assertIn("SOURCE_EVIDENCE_STALE_HOST_NATIVE_TESTS_ONLY_NO_FIRMWARE_BUILD",s)
  self.assertIn("SOURCE_EVIDENCE_CURRENT_HOST_TOOLS_ONLY",s)
  self.assertIn("source-completion-gate.py",s)
  self.assertIn("cmake --build",s)
  self.assertNotIn("sysupgrade",s)
  self.assertNotIn("mtd write",s)
  self.assertNotIn("make -j",s)
  self.assertNotIn("FLASH_PERMISSION=YES",s)
  subprocess.run(["bash","-n",str(PROVISION)],check=True,timeout=4)
 def test_firmware_completeness_gate_remains_strict(self):
  s=SOURCE.read_text()
  self.assertIn("source_hash_mismatch:",s)
  self.assertIn("build_permitted",s)
  self.assertIn("return 0 if not issues else 3",s)
  self.assertIn("source-completion-gate.py",PROVISION.read_text())
  workflow=WORKFLOW.read_text()
  self.assertIn("release-gate.py",workflow)
  self.assertIn("flash_allowed",workflow)
if __name__=="__main__":unittest.main()
