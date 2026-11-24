#!/usr/bin/env python3
"""Verify immutable source-lineage Git objects are actually present in CI checkout.

A full-depth checkout alone does NOT fetch unreferenced local commits. These
specific historical source commits are explicitly pinned by remote tags. No
missing refs are silently skipped, and no source digest is fabricated.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PINS = {
    "aa1b0b8": "aa1b0b828b05ffbe8cfa9490a967fb922b502a10",
    "331ebf7": "331ebf7fbfa5fbfa4216d53e25db134a81f62c21",
    "636710d": "636710dacdb586680c087552e342038e9f34d1bb",
    "a66f7ec": "a66f7ec0b2fa7debfa8379cafc33412304a1bde2",
    "f438b7d": "f438b7dbfcfe1c43577adcc1f8f89916447d3976",
}

def git(*args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-C", str(ROOT), *args], stderr=subprocess.PIPE, timeout=12
    )

def verify():
    for short, full in PINS.items():
        ref = "refs/tags/veci-provenance-" + short
        actual = git("rev-parse", "--verify", ref + "^{commit}").decode().strip()
        if actual != full:
            raise ValueError("PROVENANCE_REF_MISMATCH:" + ref)
        if git("cat-file", "-t", full).decode().strip() != "commit":
            raise ValueError("PROVENANCE_OBJECT_NOT_COMMIT:" + full)
        print("PINNED_ORIGINAL_COMMIT=PASS", short, full)
    for track in ("security", "system"):
        record = json.loads((ROOT / ("docs/PARALLEL_REUSE_" + track.upper() + "_20261120.json")).read_text())
        for item in record["reused_byte_identical_sources"]:
            short = item["commit"]
            if short not in PINS:
                raise ValueError("UNPINNED_ORIGINAL_COMMIT:" + short)
            original = git("show", PINS[short] + ":" + item["path"])
            if hashlib.sha256(original).hexdigest() != item["sha256"]:
                raise ValueError("PROVENANCE_SOURCE_DIGEST_MISMATCH:" + item["path"])
            if not (ROOT / item["path"]).is_file():
                raise ValueError("CURRENT_SOURCE_MISSING:" + item["path"])
    for short, names in (
        ("aa1b0b8", ("veci2-sim-lock", "sim-lock.js")),
        ("331ebf7", ("veci2-ussd", "ussd.js")),
    ):
        for name in names:
            if name.endswith(".js"):
                relative = "rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2/" + name
            else:
                relative = "rebuild/veci-v2/packages/veci-v2-runtime/" + name
            original = git("show", PINS[short] + ":" + relative)
            if (ROOT / relative).read_bytes() != original:
                raise ValueError("ORIGINAL_PIN_OR_USSD_DRIFT:" + relative)
    print("ALL_5_PROVENANCE_REFS_AND_ORIGINAL_DIGESTS=PASS")

if __name__ == "__main__":
    try:
        verify()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError) as err:
        print("PROVENANCE_BLOCKED:" + str(err), file=sys.stderr)
        sys.exit(3)
