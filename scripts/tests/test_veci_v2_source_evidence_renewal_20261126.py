"""Acceptance receipts are captured by real scoped unittest execution, never copied hashes."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
RUNNER=ROOT/"scripts/ci/renew-source-acceptance.py"
CONTRACT=ROOT/"rebuild/veci-v2/contracts/owner-final-source-evidence.json"

class ExecutedSourceEvidence(unittest.TestCase):
 def test_renewal_runs_scoped_real_tests_in_isolated_output(self):
  original=CONTRACT.read_bytes()
  with tempfile.TemporaryDirectory() as tmp:
   result=Path(tmp)/"evidence"
   run=subprocess.run(["python3",str(RUNNER),"--output",str(result),
                       "--only","ui_four_group_navigation"],
                       capture_output=True,text=True,timeout=45)
   self.assertEqual(run.returncode,0,run.stderr)
   log=(result/"logs/ui_four_group_navigation.txt").read_text()
   self.assertIn("test_login_permissions_and_logout (",log)
   self.assertIn("test_group_navigation_remains_simple (",log)
   self.assertIn("Ran 4 tests in ",log)
   self.assertTrue(log.rstrip().endswith("OK"))
   report=json.loads((result/"test-run-summary.json").read_text())
   self.assertEqual(report["accepted_modules"],1)
   self.assertEqual(report["failed_modules"],[])
   self.assertFalse((result/"owner-final-source-evidence.json").exists())
  self.assertEqual(CONTRACT.read_bytes(),original,"renewal modified tracked manifest")
 def test_full_renewal_requires_39_real_green_modules(self):
  script=RUNNER.read_text()
  for term in ("result.wasSuccessful()","result.skipped",
               "result.testsRun!=len(selections)","source_sha256",
               "log_sha256","failed_modules","len(accepted)!=len(planned)"):
   self.assertIn(term,script)
  workflow=(ROOT/".github/workflows/veci-v2-rebuild-source.yml").read_text()
  self.assertIn("renew-source-acceptance.py",workflow)
  self.assertIn("veci-source-proof",workflow)
  self.assertIn("upload-artifact",workflow)

if __name__=="__main__":unittest.main()
