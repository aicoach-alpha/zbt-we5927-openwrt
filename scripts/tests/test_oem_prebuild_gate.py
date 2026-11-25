import copy
import json
import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[2] / "rebuild/oem-updated"
sys.path.insert(0, str(BASE))
from prebuild_gate import check

class PrebuildGate(unittest.TestCase):
    def setUp(self):
        self.a = json.loads((BASE / "operation-acceptance.json").read_text())
        self.m = {"reference_sha256": self.a["reference_sha256"],
                  "operations": dict.fromkeys(self.a["operations"])}

    def test_actual_inventory_blocks_incomplete_operations(self):
        counts, blocked, gates = check(self.m, self.a)
        self.assertEqual(sum(counts.values()), 158)
        self.assertIn("get_module_status", blocked)
        self.assertIn("full_ui_integration", gates)

    def test_inventory_drift_rejected(self):
        self.m["operations"].pop("get_module_status")
        with self.assertRaises(ValueError):
            check(self.m, self.a)

    def test_missing_evidence_blocks_claimed_pass(self):
        a = copy.deepcopy(self.a)
        for row in a["operations"].values():
            row["state"] = "FUNCTIONAL_PASS"
        for gate in a["additional_gates"]:
            a["additional_gates"][gate] = True
        self.assertEqual(len(check(self.m, a)[1]), 158)
