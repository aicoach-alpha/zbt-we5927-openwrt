"""Fail-closed owner lab export: allowlisted branch and manual opt-in only."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
SRC=(ROOT/'.github/workflows/veci-v2-lab-image.yml').read_text()
class ExportGuard(unittest.TestCase):
    def test_both_stages_have_same_strict_guard(self):
        guards=[line.strip() for line in SRC.splitlines()
                if line.strip().startswith("if:") and "export_unsigned_candidate == true" in line]
        self.assertEqual(len(guards),2)
        self.assertEqual(guards[0],guards[1])
        for guard in guards:
            self.assertIn("github.event_name == 'workflow_dispatch'",guard)
            self.assertIn("inputs.export_unsigned_candidate == true",guard)
            self.assertIn("refs/heads/integration/veci-we5927-39-lte-gui-20261124",guard)
            self.assertNotIn("github.event.head_commit",guard)
    def test_no_push_path_can_export_owner_image(self):
        guards=[line.strip() for line in SRC.splitlines()
                if line.strip().startswith("if:") and "export_unsigned_candidate == true" in line]
        self.assertEqual(len(guards),2)
        for guard in guards:
            self.assertNotIn("push",guard)
            self.assertNotIn("contains(",guard)
        self.assertIn("default: false",SRC)
        self.assertIn("UNSIGNED LABORATORY IMAGE. DO NOT FLASH.",SRC)
        self.assertIn('"flash_allowed": False',SRC)
        self.assertIn("Production flash prohibited even on green CI",SRC)
if __name__=='__main__':unittest.main()
