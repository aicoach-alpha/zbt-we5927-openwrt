import sys
import struct
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ci"))
import we5927_uboot_return_branch_20261127 as x

def fixture():
    d=bytearray(4096)
    def put(off,*words):struct.pack_into("<%dI"%len(words),d,off,*words)
    put(0x100,0x3c1c0000,0x279c0700,0x0399e021,0x24020002,0x1082000b)
    put(0x810,0xbc000100,0xbc000300)
    put(0x500,0x8f990010,0x0320f809,0x24040002,0x8fbc0018,
        0x8e640000,0x8f990014,0x0320f809,0x8e450000,0x04400003)
    return d

class BranchTests(unittest.TestCase):
    def run_scan(self,data):
        with patch.object(x,"pic_scan",return_value={"gp_relative_offset":0x800,"resolved_static_patterns":[{"marker":"UPLOAD_UPGRADE","callee_candidate_offset":0x400,"callsite_offset":0x150}]}),patch.object(x,"mapping_scan",return_value={"candidates":[{"base_candidate":"0xbc000000"}]}),patch.object(x,"sink_scan",return_value={"shared_callee_candidates":[{"callee_candidate_offset":0x400,"classification":"LIKELY_MESSAGE_SINK"}]}):
            return x.inspect(data)
    def test_candidate_only(self):
        r=self.run_scan(fixture())
        self.assertEqual(len(r["candidates"]),1)
        self.assertEqual(r["candidates"][0]["next_callee_candidate_offset"],0x300)
        self.assertEqual(r["candidates"][0]["callee_semantics"],"UNKNOWN")
        self.assertFalse(r["flash_authorized"])
    def test_wrong_state(self):
        d=fixture();struct.pack_into("<I",d,0x508,0x24040003)
        self.assertEqual(self.run_scan(d)["candidates"],[])
    def test_wrong_return_register(self):
        d=fixture();struct.pack_into("<I",d,0x520,0x04600003)
        self.assertEqual(self.run_scan(d)["candidates"],[])
    def test_out_of_bounds_branch(self):
        d=fixture();struct.pack_into("<I",d,0x520,0x04407fff)
        self.assertEqual(self.run_scan(d)["candidates"],[])
    def test_wrong_argument(self):
        d=fixture();struct.pack_into("<I",d,0x51c,0x8e460000)
        self.assertEqual(self.run_scan(d)["candidates"],[])
