import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ci"))
import we5927_recovery_nor_model_20261128 as x

class NorTests(unittest.TestCase):
    def test_exact_board_partition_layout(self):
        self.assertEqual(x.FW_END-x.FW_START,0x7a0000)
        ranges=[(a,b) for _,a,b in x.PROTECTED]+[(x.FW_START,x.FW_END)]
        self.assertEqual(sorted(ranges),[(0,0x30000),(0x30000,0x40000),(0x40000,0x50000),(0x50000,0x7f0000),(0x7f0000,0x800000)])
    def test_boundary_and_rounding(self):
        self.assertEqual(x.plan(x.FW_START,1),(x.FW_START,x.FW_START+1,x.FW_START+x.ERASE_SIZE))
        self.assertEqual(x.plan(x.FW_START,x.FW_END-x.FW_START),(x.FW_START,x.FW_END,x.FW_END))
    def test_critical_or_oversized_range_rejected(self):
        for start,size in ((0,1),(0x30000,1),(0x40000,1),(x.FW_END,1),(x.FW_START-1,1),(x.FW_START,x.FW_END-x.FW_START+1),(x.FW_START,0),(x.FW_START,-1),(x.FW_START,True)):
            with self.subTest(start=start,size=size),self.assertRaises(ValueError):x.plan(start,size)
    def test_unknown_policy(self):
        with self.assertRaises(ValueError):x.plan(x.FW_START,1,"unknown")
    def test_synthetic_rounding_and_whole(self):
        image=bytes(range(256))*257
        for policy in ("rounded_payload","whole_firmware"):
            with self.subTest(policy=policy):
                r=x.simulate(image,erase_policy=policy)
                self.assertTrue(r["protected_partition_hashes_unchanged"])
                self.assertTrue(r["payload_readback_matches"])
                self.assertTrue(r["outside_erase_window_unchanged"])
                self.assertFalse(r["bootloader_behavior_verified"])
                self.assertFalse(r["flash_authorized"])
    def test_full_partition_boundary(self):
        r=x.simulate(b"\xaa"*(x.FW_END-x.FW_START))
        self.assertEqual(r["erase_end_exclusive"],x.FW_END)
        self.assertTrue(r["protected_partition_hashes_unchanged"])
