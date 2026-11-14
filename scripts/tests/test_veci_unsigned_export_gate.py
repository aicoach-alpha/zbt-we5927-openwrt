"""Prevent accidentally exposing a flash-permitted image from ordinary PR CI."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
WF = ROOT / ".github/workflows/veci-reliability-full-image-rc.yml"

class ArtifactExportPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WF.read_text()

    def test_manual_opt_in_is_false_by_default(self):
        self.assertIn("export_unsigned_candidate:", self.workflow)
        self.assertIn("default: false", self.workflow)

    def test_binary_export_has_three_independent_conditions(self):
        guard = ("github.event_name == 'workflow_dispatch' && "
                 "inputs.export_unsigned_candidate == true && "
                 "github.ref == 'refs/heads/integration/veci-reliability-rc1-20261112'")
        self.assertEqual(self.workflow.count(guard), 2)

    def test_artifact_has_do_not_flash_notice(self):
        self.assertIn("UNSIGNED_DO_NOT_FLASH.txt", self.workflow)
        self.assertIn("NOT APPROVED FOR FLASH", self.workflow)
        self.assertIn("report['flash_permission'] is False", self.workflow)

    def test_builtin_veci_installation_checked_in_rootfs(self):
        self.assertIn("BUILTIN_VECI_CORE_RPC_HTTPS_LUCI_FALLBACK=PASS", self.workflow)
        self.assertIn("LIVE_VECI_PARITY=NOT_VERIFIED", self.workflow)
        self.assertIn("source/veci-core/veci/index.html", self.workflow)
        self.assertIn("source/veci-core/rpcd-acl.json", self.workflow)
        self.assertIn("source/veci-default-ui/files/usr/sbin/veci-default-ui", self.workflow)

    def test_pr_ci_still_emits_evidence_only(self):
        self.assertIn("name: veci-we5927-rc1-build-evidence", self.workflow)
        self.assertIn("path: |", self.workflow)
        self.assertIn("__DOLLAR__{{ runner.temp }}/veci-rc1-evidence/release-gates.json".replace("__DOLLAR__", "$"), self.workflow)
        self.assertIn("__DOLLAR__{{ runner.temp }}/veci-rc1-evidence/native-features.json".replace("__DOLLAR__", "$"), self.workflow)
        self.assertIn("name: veci-we5927-RC1-UNSIGNED-DO-NOT-FLASH-", self.workflow)
        self.assertIn("if: ${{ github.event_name == 'workflow_dispatch'", self.workflow)

if __name__ == '__main__':
    unittest.main()
