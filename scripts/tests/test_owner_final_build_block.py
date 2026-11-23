import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
FLOW = (ROOT / ".github/workflows/veci-v2-lab-image.yml").read_text()
PIN = ROOT / "rebuild/veci-v2/ci/source-completion-gate.py"
SPEC = importlib.util.spec_from_file_location("owner_source_gate", PIN)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CONTRACT = json.loads((ROOT / "rebuild/veci-v2/contracts/veci-v2-rebuild-contract.json").read_text())


class OwnerBuildBlockedUntilComplete(unittest.TestCase):
    def test_owner_push_cannot_start_full_image(self):
        self.assertIn("branches-ignore:", FLOW)
        self.assertIn("- build/zbt-we2825-oem-veci-20261119", FLOW)
        self.assertLess(FLOW.index("Block incomplete owner firmware builds"),
                        FLOW.index("Install OpenWrt host dependencies"))

    def test_missing_module_blocks(self):
        issues = MODULE.audit(CONTRACT, {})
        # An empty evidence index must be refused even after all 40 source
        # modules have legitimately reached source_verified.
        self.assertTrue(any("missing_implementation_or_test_evidence:" in x for x in issues))
        self.assertIn("source_evidence_missing_or_extra_modules", issues)

    def test_fake_evidence_does_not_override_contract(self):
        data = {
            "modules": {
                x["id"]: {
                    "status": "pass",
                    "implementation_files": [".github/workflows/veci-v2-lab-image.yml"],
                    "test_ids": ["test_owner_final_build_block"],
                } for x in CONTRACT["required_core"]
            }
        }
        failures = MODULE.audit(CONTRACT, data)
        self.assertTrue(any("missing_scoped_source_acceptance:" in x for x in failures))
        self.assertTrue(any("invalid_test_reference:" in x for x in failures))

    def test_missing_or_unverified_actual_test_blocks(self):
        modified = json.loads(json.dumps(CONTRACT))
        for item in modified["required_core"]:
            item["v2_state"] = "source_verified"
        refs = {x["id"]: {
            "status": "pass",
            "implementation_files": [".github/workflows/veci-v2-lab-image.yml"],
            "test_ids": ["test_nonexistent_intentionally"],
        } for x in modified["required_core"]}
        blockers = MODULE.audit(modified, {"modules": refs})
        self.assertTrue(any(x.startswith("invalid_test_reference:") for x in blockers))


if __name__ == "__main__":
    unittest.main()
