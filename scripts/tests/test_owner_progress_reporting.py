"""Regressions for truthful module-count reporting, not feature UAT."""
from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/report_owner_module_progress.py"
SPEC = importlib.util.spec_from_file_location("owner_progress", SOURCE)
PROGRESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROGRESS)


class ProgressReporting(unittest.TestCase):
    def test_baseline_is_fixed_at_original_27(self):
        report = PROGRESS.collect()
        self.assertEqual(report["target_modules"], 27)
        self.assertEqual(len(report["modules"]), 27)
        self.assertEqual(report["required_core_total"], 40)
        self.assertEqual(report["completed"] + report["partial"] + report["pending"], 27)

    def test_no_completion_from_partial_code_or_generic_tests(self):
        report = PROGRESS.collect()
        for item in report["modules"]:
            if item["status"] == "source_verified":
                self.assertEqual(item["contract_state"], "source_verified")
                self.assertTrue(item["source_evidence"])
        self.assertEqual(len(PROGRESS.PARTIAL), 22)

    def test_no_false_promotion_when_evidence_missing(self):
        m = {"v2_state": "not_ported_to_v2"}
        self.assertFalse(PROGRESS.module_source_verified(m, {"status": "pass", "implementation_files": ["README.md"], "test_ids": ["test_fake"]}, {"test_fake"}))
        m["v2_state"] = "source_verified"
        self.assertFalse(PROGRESS.module_source_verified(m, {"status": "pass", "implementation_files": ["README.md"], "test_ids": ["test_nonexistent"]}, {"test_fake"}))
        self.assertFalse(PROGRESS.module_source_verified(m, {"status": "pass", "implementation_files": ["../../etc/passwd"], "test_ids": ["test_fake"]}, {"test_fake"}))


if __name__ == "__main__":
    unittest.main()
