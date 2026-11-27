import sys
import struct
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ci"))
import we5927_uboot_mips_xref_20261127 as x

def pair(addr,op):
    high=((addr+0x8000)>>16) if op==9 else addr>>16
    return struct.pack("<II",0x3c040000 | (high&0xffff),
                       (op<<26)|(4<<21)|(4<<16)|(addr&0xffff))

def fixture():
    b=bytearray(0x10000)
    for offset,label in [(0x8100,"HTTP_START"),(0x8220,"UPLOAD_UPGRADE")]:
        marker=x.MARKERS[label]
        b[offset:offset+len(marker)]=marker
    b[0x100:0x108]=pair(0x80008100,9)
    b[0x110:0x118]=pair(0x80008220,13)
    return b

class XrefTests(unittest.TestCase):
    def test_signed_addiu_and_ori(self):
        r=x.scan(fixture())
        self.assertEqual(r["status"],"CANDIDATE_XREFS_ONLY")
        self.assertEqual(r["candidate_groups"][0]["candidate_base"],"0x80000000")
        self.assertEqual(len(r["candidate_groups"][0]["references"]),2)
        self.assertEqual({a["pair"] for a in r["candidate_groups"][0]["references"]},
                         {"LUI_ADDIU","LUI_ORI"})
        self.assertFalse(r["flash_authorized"])
        self.assertFalse(r["release_permitted"])
        self.assertEqual(r["http_handler_control_flow"],"NOT_VERIFIED")
    def test_only_one_instruction_site_is_insufficient(self):
        b=fixture()
        b[0x110:0x118]=bytes(8)
        self.assertEqual(x.scan(b)["candidate_groups"],[])
    def test_markers_without_code_do_not_prove_handler(self):
        b=fixture()
        b[0x100:0x118]=bytes(24)
        r=x.scan(b)
        self.assertEqual(r["status"],"NO_CANDIDATE_XREFS")
        self.assertEqual(len(r["marker_labels_found"]),2)
        self.assertEqual(r["image_acceptance"],"NOT_VERIFIED")
    def test_mismatched_register_and_zero_destination_rejected(self):
        for word in (0x34648220,0x34808220):
            b=fixture()
            struct.pack_into("<I",b,0x114,word)
            self.assertEqual(x.scan(b)["candidate_groups"],[])
    def test_exact_backup_guard(self):
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/"a.bin"; b=Path(d)/"b.bin"
            a.write_bytes(fixture()); b.write_bytes(fixture())
            with self.assertRaisesRegex(ValueError,"EXACT_MTD0"):
                x.verified_scan(a,b)
            import hashlib
            with patch.object(x,"OWNER_SIZE",a.stat().st_size), patch.object(
                x,"OWNER_SHA",hashlib.sha256(a.read_bytes()).hexdigest()):
                self.assertTrue(x.verified_scan(a,b)["both_backups_verified"])
                b.write_bytes(bytes(b.stat().st_size))
                with self.assertRaisesRegex(ValueError,"EXACT_MTD0"):
                    x.verified_scan(a,b)

if __name__=="__main__":
    unittest.main()
