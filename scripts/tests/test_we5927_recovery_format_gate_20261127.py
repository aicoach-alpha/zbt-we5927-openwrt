"""Exercise real parser with synthetic OEM/OpenWrt images and fail-closed corruptions."""
import hashlib
import json
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/ci'))
from we5927_recovery_image_format_gate_20261127 import (
    analyze_image, FormatGateError,MTD3_LIMIT,DEADC0DE
)

REPORT=ROOT/'docs/VECI-V2-WE5927-EXACT-IMAGE-RECOVERY-FORMAT-20261127.json'

def image_bytes(trailer="vendor"):
    payload=b"K"*(0x17000)
    head=bytearray(struct.pack(">7I",0x27051956,0,1700000000,len(payload),
                               0x80001000,0x80001000,zlib.crc32(payload)))
    head+=bytes([5,5,2,3])+b"synthetic test".ljust(32,b"\x00")
    assert len(head)==64
    struct.pack_into(">I",head,4,zlib.crc32(head))
    sq=bytearray(96)
    struct.pack_into("<I",sq,0,0x73717368)
    struct.pack_into("<I",sq,12,1048576)
    struct.pack_into("<HH",sq,28,4,0)
    struct.pack_into("<Q",sq,40,96)
    footer=(
        b"\xff"*128+DEADC0DE if trailer=="vendor" else
        b"\xff"*128+DEADC0DE+b"metadata_version"+b"FWx0"+b"ucert" + b"X"*16
    )
    return bytes(head)+payload+bytes(sq)+footer

def inspect_buffer(data, directory):
    p=Path(directory)/"test.bin"
    p.write_bytes(data)
    return analyze_image(p,hashlib.sha256(data).hexdigest())

class OfflineUbootFormat(unittest.TestCase):
    def test_fixture_real_parser_distinguishes_oem_and_signed_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            vendor=inspect_buffer(image_bytes("vendor"),tmp)
            signed=inspect_buffer(image_bytes("signed"),tmp)
            self.assertEqual(vendor["trailer"]["class"],"OEM_STYLE_DEADC0DE_TERMINATOR")
            self.assertEqual(signed["trailer"]["class"],"OPENWRT_METADATA_SIGNATURE_TRAILER")
            self.assertTrue(vendor["trailer"]["ends_with_deadc0de"])
            self.assertTrue(signed["trailer"]["has_ucert_marker"])
            self.assertFalse(vendor["rescue_image_approved"])
            self.assertFalse(signed["rescue_image_approved"])
            self.assertEqual(signed["bootloader_http_acceptance"],"NOT_VERIFIED")

    def test_validated_image_rejects_mutated_crc_magic_rootfs_sha_and_size(self):
        source=bytearray(image_bytes("vendor"))
        mutations={
            "corrupt_header":(8,0x01,"UIMAGE_HEADER_CRC32_MISMATCH"),
            "corrupt_payload":(64+20,0x01,"UIMAGE_DATA_CRC32_MISMATCH"),
            "corrupt_magic":(0,0x01,"UIMAGE_MAGIC_NOT_FOUND"),
            "corrupt_rootfs_magic":(64+0x17000,0x01,"SQUASHFS_NOT_IMMEDIATELY_AFTER_UIMAGE"),
            "corrupt_rootfs_bytes_used":(64+0x17000+47,0xFF,"SQUASHFS_BYTES_USED_OUT_OF_BOUNDS")
        }
        with tempfile.TemporaryDirectory() as tmp:
            for name,(offset,delta,want) in mutations.items():
                broken=source.copy()
                broken[offset]^=delta
                with self.subTest(name=name):
                    with self.assertRaisesRegex(FormatGateError,want):
                        inspect_buffer(bytes(broken),tmp)
            file=Path(tmp)/"test.bin"
            file.write_bytes(source)
            with self.assertRaisesRegex(FormatGateError,"IMAGE_SHA256_MISMATCH"):
                analyze_image(file,"0"*64)
            with self.assertRaisesRegex(FormatGateError,"IMAGE_SIZE_OUT_OF_FLASH_BOUNDS"):
                inspect_buffer(bytes(source)+b"\x00"*(MTD3_LIMIT-len(source)+1),tmp)

    def test_ambiguous_trailers_are_never_oem_or_approved(self):
        base = image_bytes("vendor")[:-4]
        tails = (b"ucert"+DEADC0DE, b"FWx0"+DEADC0DE,
                 b"FWx0ucert"+DEADC0DE, b"FWx0", b"ucert", b"")
        with tempfile.TemporaryDirectory() as tmp:
            for tail in tails:
                with self.subTest(tail=tail):
                    result = inspect_buffer(base+tail, tmp)
                    self.assertEqual(result["trailer"]["class"],
                                     "UNRECOGNIZED_OR_MIXED_TRAILER")
                    self.assertFalse(result["rescue_image_approved"])
                    self.assertEqual(result["bootloader_http_acceptance"], "NOT_VERIFIED")

    def test_squashfs_bytes_used_boundary_not_arbitrary_byte_mutation(self):
        source = bytearray(image_bytes("vendor"))
        sq_offset = 64+0x17000
        with tempfile.TemporaryDirectory() as tmp:
            for size in (96, 97, len(source)-sq_offset):
                with self.subTest(size=size):
                    struct.pack_into("<Q", source, sq_offset+40, size)
                    result = inspect_buffer(bytes(source), tmp)
                    self.assertEqual(result["squashfs"]["bytes_used"], size)
                    self.assertFalse(result["rescue_image_approved"])
            for size in (0, 95, len(source)-sq_offset+1):
                with self.subTest(size=size):
                    struct.pack_into("<Q", source, sq_offset+40, size)
                    with self.assertRaisesRegex(FormatGateError,
                                                "SQUASHFS_BYTES_USED_OUT_OF_BOUNDS"):
                        inspect_buffer(bytes(source), tmp)

    def test_real_binary_receipt_proves_format_divergence_not_restore(self):
        receipt=json.loads(REPORT.read_text())
        v=receipt["sources"]["vendor_reference"]
        c=receipt["sources"]["signed_veci_sysupgrade"]
        self.assertEqual(v["sha256"],"80529b8e9c31d686eb7f63a1517d6dbcf781f26cb4aceb7b8b1ff27c2d51d1f9")
        self.assertEqual(c["sha256"],"3adc815e77a7c9b0e25f742601eb2dc94423aad540b26efa86423821a667abb1")
        self.assertEqual(v["trailer"]["class"],"OEM_STYLE_DEADC0DE_TERMINATOR")
        self.assertEqual(c["trailer"]["class"],"OPENWRT_METADATA_SIGNATURE_TRAILER")
        self.assertFalse(receipt["same_trailer_format"])
        self.assertFalse(receipt["release_permitted"])
        self.assertFalse(receipt["flash_authorized"])
        self.assertFalse(receipt["upload_to_uboot_webfailsafe_safe_as_test"])
        self.assertEqual(receipt["recovery_image_format_in_bootloader"],"UNKNOWN")

if __name__=="__main__":
    unittest.main()
