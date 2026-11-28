import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ci"))
import we5927_uboot_pic_got_20261127 as x

def fixture():
    d=bytearray(8192)
    def put(off,*words):struct.pack_into("<%dI"%len(words),d,off,*words)
    base=0xbc000000; gp=0x1000
    for i in range(16):
        off=0x800+i*8
        put(off,base+off-4,base+off+4)
    for off in range(0x100,0x200,0x20):
        put(off,0x3c1c0000,0x279c0000|(gp-off),0x0399e021)
    marker=x.MARKERS["HTTP_READY"]
    d[0x620:0x620+len(marker)]=marker
    put(gp+0x10,base+0x600)
    put(gp+0x20,base+0x400)
    put(0x300,0x8f840010,0x8f990020,0x10000001,0x24840020,0x0320f809,0)
    return d

class PicTests(unittest.TestCase):
    def test_exact_pattern(self):
        r=x.inspect(fixture())
        self.assertEqual(r["gp_consensus_votes"],8)
        self.assertEqual(len(r["resolved_static_patterns"]),1)
        self.assertEqual(r["resolved_static_patterns"][0]["marker"],"HTTP_READY")
        self.assertFalse(r["flash_authorized"])
        self.assertEqual(r["image_acceptance"],"NOT_VERIFIED")
    def test_wrong_branch_target_rejected(self):
        d=fixture();struct.pack_into("<I",d,0x308,0x10000002)
        self.assertEqual(x.inspect(d)["resolved_static_patterns"],[])
    def test_wrong_delay_slot_rejected(self):
        d=fixture();struct.pack_into("<I",d,0x30c,0x24840021)
        self.assertEqual(x.inspect(d)["resolved_static_patterns"],[])
    def test_gp_disagreement_rejected(self):
        d=fixture();struct.pack_into("<I",d,0x104,0x279c0f01)
        self.assertEqual(x.inspect(d)["gp_consensus_votes"],0)
        self.assertEqual(x.inspect(d)["resolved_static_patterns"],[])
    def test_no_mapping_rejected(self):
        d=fixture();d[0x800:0x880]=bytes(128)
        self.assertEqual(x.inspect(d)["resolved_static_patterns"],[])
