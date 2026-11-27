#!/usr/bin/env python3
"""Offline WE5927 OEM-vs-VeCI image format evidence (not a U-Boot upload test).

Reads local firmware image bytes only. Never builds, converts, signs, uploads,
flashes, restores, or contacts a router. Importable for fully synthetic tests.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib

MTD3_LIMIT = 0x7A0000  # exact owner router
SQUASHFS_MIN_SUPERBLOCK = 96
UIMAGE_MAGIC = 0x27051956
DEADC0DE = bytes.fromhex("deadc0de")
FWMETA_MARK = b"FWx0"
VENDOR_SHA = "80529b8e9c31d686eb7f63a1517d6dbcf781f26cb4aceb7b8b1ff27c2d51d1f9"
VECI_SHA = "3adc815e77a7c9b0e25f742601eb2dc94423aad540b26efa86423821a667abb1"


class FormatGateError(ValueError):
    pass


def analyze_image(path, expected_sha):
    binary = Path(path).read_bytes()
    size = len(binary)
    if not (SQUASHFS_MIN_SUPERBLOCK + 64 <= size <= MTD3_LIMIT):
        raise FormatGateError("IMAGE_SIZE_OUT_OF_FLASH_BOUNDS")
    sha256 = hashlib.sha256(binary).hexdigest()
    if sha256 != expected_sha:
        raise FormatGateError("IMAGE_SHA256_MISMATCH")
    hdr = bytearray(binary[:64])
    magic, expected_hcrc, stamp, payload_size, load, entry, expected_dcrc = struct.unpack_from(">7I", hdr)
    if magic != UIMAGE_MAGIC:
        raise FormatGateError("UIMAGE_MAGIC_NOT_FOUND")
    if payload_size <= 0 or payload_size + 64 + SQUASHFS_MIN_SUPERBLOCK > size:
        raise FormatGateError("UIMAGE_PAYLOAD_OUT_OF_BOUNDS")
    hdr[4:8] = bytes(4)
    calc_hcrc = zlib.crc32(hdr) & 0xFFFFFFFF
    calc_dcrc = zlib.crc32(binary[64:64+payload_size]) & 0xFFFFFFFF
    if calc_hcrc != expected_hcrc:
        raise FormatGateError("UIMAGE_HEADER_CRC32_MISMATCH")
    if calc_dcrc != expected_dcrc:
        raise FormatGateError("UIMAGE_DATA_CRC32_MISMATCH")
    metadata = list(binary[28:32])
    if metadata[:3] != [5,5,2]:
        raise FormatGateError("NOT_LINUX_MIPS_KERNEL")
    sq_offset = 64 + payload_size
    if binary[sq_offset:sq_offset+4] != b"hsqs":
        raise FormatGateError("SQUASHFS_NOT_IMMEDIATELY_AFTER_UIMAGE")
    sq_major, sq_minor = struct.unpack_from("<HH", binary, sq_offset+28)
    sq_block_size = struct.unpack_from("<I", binary, sq_offset+12)[0]
    sq_block_log = struct.unpack_from("<H", binary, sq_offset+22)[0]
    if not (12 <= sq_block_log <= 20 and sq_block_size == 1 << sq_block_log):
        raise FormatGateError("SQUASHFS_INVALID_BLOCK_GEOMETRY")
    sq_bytes_used = struct.unpack_from("<Q", binary, sq_offset+40)[0]
    if (sq_major,sq_minor) != (4,0):
        raise FormatGateError("SQUASHFS_VERSION_NOT_4_0")
    if (sq_bytes_used < SQUASHFS_MIN_SUPERBLOCK or
        sq_offset + sq_bytes_used > size):
        raise FormatGateError("SQUASHFS_BYTES_USED_OUT_OF_BOUNDS")
    tail = binary[sq_offset+sq_bytes_used:]
    has_fwx = FWMETA_MARK in tail
    has_ucert = b"ucert" in tail
    deadc0de_indices = []
    cursor = 0
    while True:
        found = tail.find(DEADC0DE, cursor)
        if found < 0:
            break
        deadc0de_indices.append(sq_offset+sq_bytes_used+found)
        cursor = found + len(DEADC0DE)
    if (not has_fwx and not has_ucert and tail.endswith(DEADC0DE)):
        trailer_class = "OEM_STYLE_DEADC0DE_TERMINATOR"
    elif has_fwx and has_ucert and not tail.endswith(DEADC0DE):
        trailer_class = "OPENWRT_METADATA_SIGNATURE_TRAILER"
    else:
        trailer_class = "UNRECOGNIZED_OR_MIXED_TRAILER"
    return {
        "size_bytes":size,
        "sha256":sha256,
        "uimage":{"magic":"27051956","payload_bytes":payload_size,
                  "header_crc32":"PASS","data_crc32":"PASS",
                  "os_arch_type_comp":metadata},
        "squashfs":{"offset":sq_offset,"major":sq_major,"minor":sq_minor,
                    "bytes_used":sq_bytes_used,"block_size":sq_block_size},
        "trailer":{"bytes_after_squashfs":len(tail),"class":trailer_class,
                   "deadc0de_offsets":deadc0de_indices,
                   "has_openwrt_fwx0_marker":has_fwx,
                   "has_ucert_marker":has_ucert,
                   "ends_with_deadc0de":tail.endswith(DEADC0DE)},
        "within_exact_mtd3_size":size<=MTD3_LIMIT,
        "image_source_verified_by_sha256":True,
        "bootloader_http_acceptance":"NOT_VERIFIED",
        "physical_recovery_test":"NOT_RUN",
        "rescue_image_approved":False,
    }


def compare(vendor, veci):
    v = analyze_image(vendor,VENDOR_SHA)
    c = analyze_image(veci,VECI_SHA)
    return {
        "schema":"we5927-offline-recovery-format-parity.v1",
        "method":"exact-size and SHA256, uImage CRC32, SquashFS superblock, trailer marker inventory",
        "sources":{"vendor_reference":v,"signed_veci_sysupgrade":c},
        "both_valid_uimage_crc":True,
        "both_have_squashfs_4_0":True,
        "same_outer_uimage_and_squashfs_structure":True,
        "same_trailer_format":v["trailer"]["class"] == c["trailer"]["class"],
        "recovery_image_format_in_bootloader":"UNKNOWN",
        "upload_to_uboot_webfailsafe_safe_as_test":False,
        "format_does_not_prove_bootloader_compatibility":True,
        "owner_router_touched":False,
        "flash_authorized":False,
        "release_permitted":False,
        "blocking_reason":"WEB_FAILSAFE_UPLOAD_CAN_TRIGGER_FLASH; UBOOT_HANDLER_ACCEPTANCE_NOT_TESTED",
        "next_evidence":"offline bootloader HTTP handler/static parser analysis or approved real physical recovery proof",
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--vendor",required=True)
    parser.add_argument("--veci",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    evidence=compare(args.vendor,args.veci)
    output=Path(args.output)
    if output.exists():
        raise SystemExit("STOP=REFUSE_TO_OVERWRITE_EXISTING_RECEIPT")
    output.write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+"\n")
    print("EXACT_VENDOR_IMAGE_UIMAGE_AND_SQUASHFS=PASS")
    print("EXACT_VECI_SIGNED_UIMAGE_AND_SQUASHFS=PASS")
    print("TRAILERS_FORMAT_SAME="+("YES" if evidence["same_trailer_format"] else "NO"))
    print("VENDOR_TRAILER_CLASS="+evidence["sources"]["vendor_reference"]["trailer"]["class"])
    print("VECI_TRAILER_CLASS="+evidence["sources"]["signed_veci_sysupgrade"]["trailer"]["class"])
    print("RECOVERY_UPLOAD_ACCEPTANCE=NOT_VERIFIED; FLASH_AUTHORIZED=NO")
    print("OFFLINE_RECEIPT="+str(output))

if __name__=="__main__":
    main()
