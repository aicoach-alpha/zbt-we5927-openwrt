"""Ensure owner laboratory export stays manual/unsigned only."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = (ROOT / '.github/workflows/veci-v2-lab-image.yml').read_text()

class ExportGuard(unittest.TestCase):
    def test_both_stages_same_guard(self):
        owner = "(github.ref == 'refs/heads/build/zbt-we2825-oem-veci-20261119' && ((github.event_name == 'workflow_dispatch' && inputs.export_unsigned_candidate == true) || (github.event_name == 'push' && contains(github.event.head_commit.message, '[export-unsigned-veci-v2]'))))"
        prepare, upload = SRC.split("      - name: Upload explicit unsigned image", 1)
        self.assertIn(owner, prepare)
        self.assertIn("id: prepare_candidate", prepare)
        self.assertIn("if: ${{ steps.prepare_candidate.outcome == 'success' }}", upload)
        self.assertIn("if-no-files-found: error", upload)
        self.assertNotIn("github.ref", upload)

    def test_gui_branch_uses_explicit_dispatch_and_rejects_automatic_compiles(self):
        branch = "feat/veci-v2-native-gui-refresh-20261126"
        self.assertIn(f"(github.ref == 'refs/heads/{branch}' && github.event_name == "
                      "'workflow_dispatch' && inputs.export_unsigned_candidate == true)", SRC)
        push = SRC.split("  push:", 1)[1].split("    paths:", 1)[0]
        self.assertIn("branches-ignore:", push)
        self.assertIn(f"      - {branch}", push)

    def test_ordinary_push_does_not_export_owner_image(self):
        self.assertIn("contains(github.event.head_commit.message, '[export-unsigned-veci-v2]')", SRC)
        self.assertIn("default: false", SRC)
        self.assertIn("UNSIGNED LABORATORY IMAGE. DO NOT FLASH.", SRC)
        self.assertIn("flash_allowed\": False", SRC)
        self.assertIn("Production flash prohibited even on green CI", SRC)

if __name__ == '__main__':
    unittest.main()
