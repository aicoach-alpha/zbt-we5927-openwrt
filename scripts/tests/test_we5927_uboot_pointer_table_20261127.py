import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ci"))
import we5927_uboot_pointer_table_20261127 as x

class TableTests(unittest.TestCase):
    def fixture(self,n):
        d=bytearray(4096)
        base=0xbc000000
        for i in range(n):
            off=0x100+i*8
            struct.pack_into("<II",d,off,base+off-4,base+off+4)
        marker=x.MARKERS["TFTP"]
        d[0x500:0x500+len(marker)]=marker
        struct.pack_into("<I",d,0x700,base+0x500)
        return d
    def test_linked_table_and_marker(self):
        r=x.inspect(self.fixture(32))
        self.assertEqual(r["status"],"CANDIDATE_MAPPING_ONLY")
        c=[g for g in r["candidates"] if g["base_candidate"]=="0xbc000000"]
        self.assertTrue(c)
        self.assertEqual(c[0]["direct_marker_pointer_offsets"]["TFTP"],[0x700])
        self.assertFalse(r["flash_authorized"])
        self.assertEqual(r["image_acceptance"],"NOT_VERIFIED")
    def test_short_run_not_evidence(self):
        self.assertEqual(x.inspect(self.fixture(15))["candidates"],[])
    def test_zeros_not_evidence(self):
        self.assertEqual(x.inspect(bytes(4096))["candidates"],[])
