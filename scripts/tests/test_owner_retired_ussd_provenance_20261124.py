"""Retired USSD must never return as a runtime requirement or ROM binary."""
import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
PIN=ROOT/"scripts/ci/verify-provenance-refs.py"
ROM=ROOT/"rebuild/veci-v2/ci/check-all-core-rom.py"
class RetiredUssdProvenance(unittest.TestCase):
    def test_original_git_commit_still_verified_but_runtime_absent(self):
        source=PIN.read_text()
        self.assertIn('"331ebf7": "331ebf7fbfa5fbfa4216d53e25db134a81f62c21"',source)
        self.assertIn("RETIRED_USSD_REINTRODUCED",source)
        self.assertIn("for rel in retired:",source)
        result=subprocess.run(["python3",str(PIN)],cwd=ROOT,
            capture_output=True,text=True,timeout=22)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn("ALL_5_PROVENANCE_REFS_AND_ORIGINAL_DIGESTS=PASS",result.stdout)
    def test_flash_image_mapping_does_not_require_ussd(self):
        self.assertNotIn('"lte_ussd":',ROM.read_text())
        self.assertFalse((ROOT/"rebuild/veci-v2/packages/veci-v2-runtime/veci2-ussd").exists())
        self.assertFalse((ROOT/"rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2/ussd.js").exists())
if __name__=="__main__":unittest.main()
