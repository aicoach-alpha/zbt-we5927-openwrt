import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ci"))
import we5927_recovery_retry_20261128 as x
class RetryTests(unittest.TestCase):
    def test_whole_restore_after_all_interruptions(self):
        for stage in x.STAGES:
            r=x.experiment(b"A"*70000,b"B"*200000,"rounded_payload","whole_firmware",stage)
            self.assertTrue(r["entire_firmware_partition_restored"])
            self.assertTrue(r["protected_hashes_unchanged"])
            self.assertEqual(r["bootability"],"UNKNOWN")
            self.assertFalse(r["flash_authorized"])
    def test_rounded_retry_may_leave_residue(self):
        r=x.experiment(b"A"*10000,b"B"*200000,"whole_firmware","rounded_payload","mid_program")
        self.assertTrue(r["restore_payload_exact"])
        self.assertFalse(r["entire_firmware_partition_restored"])
    def test_invalid_stage(self):
        with self.assertRaises(ValueError):x.experiment(b"A",b"B","whole_firmware","whole_firmware","invalid")
