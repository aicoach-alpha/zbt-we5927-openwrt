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
    def test_native_source_tests_run_after_pinned_host_dependencies(self):
        full=WF.read_text()
        source_only=(ROOT/".github/workflows/veci-v2-rebuild-source.yml").read_text()
        for workflow in (full,source_only):
            self.assertLess(workflow.index("source-completion-gate.py"),
                            workflow.index("Install "))
            self.assertLess(workflow.index("Install "),
                            workflow.index("provision-native-uci-tests.sh"))
            self.assertLess(workflow.index("provision-native-uci-tests.sh"),
                            workflow.index("python3 -m unittest discover -s scripts/tests"))
            self.assertIn('source "$RUNNER_TEMP/veci-host-test-tools/native-test-env.sh"',workflow)
            self.assertIn("verify-provenance-refs.py",workflow)
        self.assertLess(full.index("python3 -m unittest discover -s scripts/tests"),
                        full.index("Pin, stage and verify exact 2SIM board sources"))

    def test_not_flash_approved_and_explicitly_gated(self):
        s=WF.read_text()
        for token in ("default: false","UNSIGNED LABORATORY IMAGE. DO NOT FLASH.",
                      '"flash_allowed": False','"signing_and_trust_anchor": "not_verified"',
                      "retention-days: 14","Block incomplete owner firmware builds before any compilation"):
            self.assertIn(token,s)
if __name__=="__main__":unittest.main()
