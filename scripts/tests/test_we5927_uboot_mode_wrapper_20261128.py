import sys
import struct
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ci"))
import we5927_uboot_mode_wrapper_20261128 as x

def fixture():
    d=bytearray(4096);p=[0]*53
    items={7:0x00808021,9:0x24020001,11:0x14a20009,18:0x8f990010,23:0x14a00009,28:0x02003021,29:0x3c048100,30:0x8f990010,31:0x1000000c,32:0x3c050005,33:0x24020002,34:0x14a2000d,42:0x8f990010,44:0x8fbf001c,45:0x8fb00018,46:0x03200008,47:0x27bd0020,50:0x2402ffff,51:0x03e00008}
    for k,v in items.items():p[k]=v
    struct.pack_into("<53I",d,0x100,*p);struct.pack_into("<I",d,0x810,0xbc000600)
    return d
class WrapperTests(unittest.TestCase):
    def run_scan(self,d):
        with patch.object(x,"branch_scan",return_value={"candidates":[{"next_callee_candidate_offset":0x100}]}),patch.object(x,"pic_scan",return_value={"gp_relative_offset":0x800}),patch.object(x,"mapping_scan",return_value={"candidates":[{"base_candidate":"0xbc000000"}]}):
            return x.inspect(d)
    def test_pattern(self):
        r=self.run_scan(fixture());self.assertEqual(len(r["candidates"]),1)
        self.assertTrue(r["candidates"][0]["destination_matches_expected_firmware_start"])
        self.assertFalse(r["flash_authorized"])
    def test_different_destination_not_certified(self):
        d=fixture();struct.pack_into("<I",d,0x100+32*4,0x3c050004)
        r=self.run_scan(d);self.assertFalse(r["candidates"][0]["destination_matches_expected_firmware_start"])
    def test_wrong_branch(self):
        d=fixture();struct.pack_into("<I",d,0x100+31*4,0x10000001)
        self.assertEqual(self.run_scan(d)["candidates"],[])
    def test_wrong_indirect_target(self):
        d=fixture();struct.pack_into("<I",d,0x100+30*4,0x8f990014)
        self.assertEqual(self.run_scan(d)["candidates"],[])
    def test_wrong_length_argument(self):
        d=fixture();struct.pack_into("<I",d,0x100+28*4,0x02403021)
        self.assertEqual(self.run_scan(d)["candidates"],[])
