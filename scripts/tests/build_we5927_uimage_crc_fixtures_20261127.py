"""Generate synthetic 8MB WE5927 legacy uImage fixtures for Windows CI only."""
import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path

MTD3_BYTES = 7995392
PAYLOAD_BYTES = 1959054
HEADER_BYTES = 64

def create(path: Path, corrupt: str) -> None:
    payload = bytearray(bytes([x % 251 for x in range(251)]) * (PAYLOAD_BYTES // 251 + 1))
    del payload[PAYLOAD_BYTES:]
    dcrc = zlib.crc32(payload) & 0xffffffff
    name = b"VEcI synthetic test only".ljust(32,b"\x00")
    header = bytearray(struct.pack(">7I4B32s", 0x27051956, 0, 1700000000, PAYLOAD_BYTES,
                                   0x80001000, 0x80001000, dcrc, 5, 5, 2, 3, name))
    assert len(header)==HEADER_BYTES
    hcrc=zlib.crc32(header) & 0xffffffff
    struct.pack_into(">I",header,4,hcrc)
    if corrupt=="header":
        header[8] ^= 1
    elif corrupt=="magic":
        header[0] ^= 0x80
    elif corrupt not in ("none","payload"):
        raise ValueError(corrupt)
    blob=bytearray(header+payload)
    if corrupt=="payload":
        blob[64+123] ^= 1
    blob.extend(b"\xff" * (MTD3_BYTES - len(blob)))
    assert len(blob)==MTD3_BYTES
    path.write_bytes(blob)
    digest=hashlib.sha256(blob).hexdigest()
    receipt={
      "schema":"we5927-readonly-current-mtd3-backup.v1",
      "date_local":"SYNTHETIC_TEST_ONLY",
      "image_kind":"RAW_MTD3_NOT_A_SYSUPGRADE_IMAGE",
      "board":"zbtlink,zbt-we5927",
      "bytes":MTD3_BYTES,
      "sha256":digest,
      "remote_hash_before_match":True,
      "remote_hash_after_match":True,
      "firmware_flash_authorized":False,
      "image_path":str(path.resolve()),
    }
    path.with_suffix(".json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    print(f"SYNTHETIC_{corrupt.upper()}_IMAGE={path}")

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    dst=Path(args.output)
    dst.mkdir(parents=True,exist_ok=True)
    for test in ("none","header","payload","magic"):
        create(dst / f"synthetic-we5927-{test}.bin",test)

if __name__=="__main__":
    main()
