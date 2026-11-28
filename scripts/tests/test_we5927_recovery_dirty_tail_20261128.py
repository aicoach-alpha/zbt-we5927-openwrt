import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ci"))
import we5927_recovery_dirty_tail_20261128 as x
class DirtyTailTests(unittest.TestCase):
    def test_whole_erase_clean_is_not_original_restore(self):
        r=x.experiment(b"A"*70000,b"B"*200000,"rounded_payload","whole_firmware","mid_program")
        self.assertTrue(r["restore_payload_exact"])
        self.assertTrue(r["tail_all_erased"])
        self.assertFalse(r["original_partition_exact"])
        self.assertFalse(r["original_tail_exact"])
        self.assertEqual(r["configuration_restore"],"NOT_VERIFIED")
    def test_rounded_retry_may_keep_dirty_tail(self):
        r=x.experiment(b"A"*70000,b"B"*200000,"rounded_payload","rounded_payload","mid_program")
        self.assertGreater(r["tail_non_erased_bytes"],0)
        self.assertFalse(r["tail_all_erased"])
        self.assertTrue(r["protected_hashes_unchanged"])
        self.assertFalse(r["flash_authorized"])
    def test_aligned_payload_first_sector_preserves_original_tail(self):
        r=x.experiment(b"A"*65536,b"B"*200000,"rounded_payload","rounded_payload","first_sector_erased")
        self.assertTrue(r["original_partition_exact"])
        self.assertFalse(r["tail_all_erased"])
    def test_bad_stage_and_type(self):
        for old,stage in ((b"A","unknown"),(bytearray(b"A"),"mid_program")):
            with self.assertRaises(ValueError):x.experiment(old,b"B","whole_firmware","whole_firmware",stage)
