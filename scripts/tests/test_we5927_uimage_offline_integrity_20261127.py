"""Guard zero-router-access and real legacy header CRC fixture construction."""
import json
import re
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from build_we5927_uimage_crc_fixtures_20261127 import create, MTD3_BYTES, PAYLOAD_BYTES

ROOT=Path(__file__).resolve().parents[2]
PS1=ROOT/"scripts/veci-we5927-uimage-offline-integrity-20261127.ps1"

class UimageOffline(unittest.TestCase):
    def test_fixture_positive_and_negative_crc(self):
        with tempfile.TemporaryDirectory() as directory:
            for corrupt in ("none","header","payload","magic"):
                file=Path(directory)/(corrupt+".bin")
                create(file,corrupt)
                self.assertEqual(file.stat().st_size,MTD3_BYTES)
                data=file.read_bytes()
                magic,hcrc,timestamp,size,load,entry,dcrc=struct.unpack(">7I",data[:28])
                header=bytearray(data[:64])
                header[4:8]=b"\x00"*4
                hdr_ok=(zlib.crc32(header)&0xffffffff)==hcrc
                data_ok=(zlib.crc32(data[64:64+size])&0xffffffff)==dcrc
                self.assertEqual(hdr_ok,corrupt not in ("header","magic"))
                self.assertEqual(data_ok,corrupt!="payload")
                self.assertEqual(size,PAYLOAD_BYTES)
                self.assertEqual(magic==0x27051956,corrupt!="magic")
                self.assertEqual(json.loads(file.with_suffix(".json").read_text())["bytes"],MTD3_BYTES)

    def test_only_offline_windows_sources_no_network_or_flash(self):
        s=PS1.read_text()
        for expected in ("LOCAL_BACKUP_AND_RECEIPT_SHA256=PASS",
                         "UIMAGE_HEADER_CRC32=PASS","UIMAGE_DATA_CRC32=PASS",
                         "CRC_RANGE_OUT_OF_BOUNDS",
                         "STOP=UIMAGE_HEADER_CRC32_MISMATCH",
                         "STOP=UIMAGE_DATA_CRC32_MISMATCH",
                         "RAW_MTD3_NOT_FLASHABLE=YES",
                         "BOOTLOADER_RESTORE_FORMAT=NOT_VERIFIED"):
            self.assertIn(expected,s)
        executable="\n".join(line for line in s.splitlines() if not line.lstrip().startswith("#"))
        for forbidden in (r"\bssh(?:\.exe)?\b",r"\bscp(?:\.exe)?\b",r"\bsysupgrade\s+",
                          r"\bmtd\s+(?:write|erase)\b",r"\bflash_erase\b",
                          r"\buci\s+(?:set|commit)\b",r"\breboot\s+",
                          r"\bStart-Process\b",r"\bInvoke-Expression\b"):
            self.assertIsNone(re.search(forbidden,executable,flags=re.I),forbidden)
        self.assertIn("RAW_IMAGE_SHA256_MISMATCH",s)
        self.assertIn("UIMAGE_METADATA",s)
        self.assertIn("UIMAGE_ARCH_CODE",s)

if __name__=="__main__":
    unittest.main()
