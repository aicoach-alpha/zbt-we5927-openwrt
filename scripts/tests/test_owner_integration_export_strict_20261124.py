"""Unsigned integration image export needs exact branch + manual opt-in."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
WF=ROOT/".github/workflows/veci-v2-lab-image.yml"
BRANCH="refs/heads/integration/veci-we5927-39-lte-gui-20261124"
class OwnerIntegrationExportPolicy(unittest.TestCase):
    def test_two_explicit_export_steps_only(self):
        s=WF.read_text()
        conditions=[x.strip() for x in s.splitlines() if x.strip().startswith("if:") and "export_unsigned_candidate == true" in x]
        self.assertEqual(len(conditions),2)
        for guard in conditions:
            self.assertIn("workflow_dispatch",guard)
            self.assertIn("inputs.export_unsigned_candidate == true",guard)
            self.assertIn(BRANCH,guard)
            self.assertNotIn("github.event.head_commit",guard)
            self.assertNotIn("'push'",guard)
    def test_not_flash_approved_and_explicitly_gated(self):
        s=WF.read_text()
        for token in ("default: false","UNSIGNED LABORATORY IMAGE. DO NOT FLASH.",
                      '"flash_allowed": False','"signing_and_trust_anchor": "not_verified"',
                      "retention-days: 14","Block incomplete owner firmware builds before any compilation"):
            self.assertIn(token,s)
if __name__=="__main__":unittest.main()
