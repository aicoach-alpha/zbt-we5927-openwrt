"""No source verification from filenames, fake receipts, or drifted hashes."""
import importlib.util
import json
from pathlib import Path
import hashlib
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/"rebuild/veci-v2/ci/source-completion-gate.py"
spec=importlib.util.spec_from_file_location("strict_source_gate",SOURCE)
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
base=json.loads((ROOT/"rebuild/veci-v2/contracts/veci-v2-rebuild-contract.json").read_text())


class FailClosedSourceEvidence(unittest.TestCase):
    def test_real_missing_39_core_evidence_still_blocks(self):
        problems=gate.audit(base,{})
        self.assertTrue(any("source_evidence_missing_or_extra_modules"==x for x in problems))
        self.assertTrue(any("not_source_verified" in x for x in problems))

    def test_verified_module_cannot_use_an_unrelated_test_or_fake_log(self):
        contract=json.loads(json.dumps(base))
        target=next(item for item in contract["required_core"] if item["id"]=="lte_apn_pin_puk")
        target["v2_state"]="source_verified"
        impl="rebuild/veci-v2/packages/veci-v2-runtime/veci2-sim-lock"
        case="scripts/tests/test_last_pin_source.py"
        files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in (impl,case)}
        record=dict(status="pass",implementation_files=[impl],test_source_files=[case],
            source_sha256=files,test_ids=["test_pty_fake_modem_one_shot_timeout_cancel_and_rejects"],
            receipt={"kind":"executed_source_tests","exit_code":0,
                     "hardware_uat":"not_run","log_file":"docs/NO_SUCH_LOG.txt",
                     "log_sha256":"0"*64})
        evidence={"modules":{"lte_apn_pin_puk":record}}
        problems=gate.audit(contract,evidence)
        self.assertIn("invalid_source_test_receipt:lte_apn_pin_puk",problems)
        self.assertIn("test_not_scoped_to_module:lte_apn_pin_puk",problems)

    def test_unrelated_skipped_and_failed_receipts_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "receipt.txt"
            for line in ("test_other (case.Other) ... ok",
                         "test_target (case.Target) ... skipped 'unavailable'",
                         "test_target (case.Target) ... FAIL"):
                with self.subTest(line=line):
                    log.write_text(line + "\nRan 1 test in 0.01s\n\nOK\n")
                    self.assertFalse(gate.receipt_passed(log, ["test_target"]))

    def test_modified_source_and_path_traversal_are_refused(self):
        contract=json.loads(json.dumps(base))
        target=next(item for item in contract["required_core"] if item["id"]=="lte_apn_pin_puk")
        target["v2_state"]="source_verified"
        rec={"status":"pass","implementation_files":["../../etc/passwd"],
             "test_ids":["test_real_missing_39_core_evidence_still_blocks"],
             "test_source_files":["scripts/tests/test_owner_source_evidence_integrity.py"],
             "source_sha256":{"../../etc/passwd":"0"*64,
                   "scripts/tests/test_owner_source_evidence_integrity.py":"0"*64},
             "receipt":{"kind":"executed_source_tests","exit_code":0,
                        "hardware_uat":"not_run","log_file":"../../etc/passwd",
                        "log_sha256":"0"*64}}
        problems=gate.audit(contract,{"modules":{"lte_apn_pin_puk":rec}})
        self.assertTrue(any("missing_or_unsafe_implementation_file:lte_apn_pin_puk"==x for x in problems))
        self.assertTrue(any("source_hash_mismatch:lte_apn_pin_puk"==x for x in problems))
        self.assertTrue(any("invalid_source_test_receipt:lte_apn_pin_puk"==x for x in problems))


if __name__=="__main__":
    unittest.main()
