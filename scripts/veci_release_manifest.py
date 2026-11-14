#!/usr/bin/env python3
"""Embed reviewed source identity in the image; NEVER assert signed/released."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

HEX40 = re.compile(r"^[0-9a-f]{40}$")
BOARD = "zbtlink,zbt-we5927"
TARGET = "ramips/mt76x8"
OPENWRT_VERSION = "25.12.5"


def create_manifest(source_commit, openwrt_pin):
    if not HEX40.fullmatch(source_commit) or not HEX40.fullmatch(openwrt_pin):
        raise ValueError("invalid source commit or OpenWrt pin")
    return {
        "schema": 1,
        "board": BOARD,
        "target": TARGET,
        "version": OPENWRT_VERSION,
        "build_id": source_commit,
        "openwrt_source_sha": openwrt_pin,
        "channel": "development",
        "image_signature": "not_verified",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--expected-head", default="")
    args = parser.parse_args(argv)
    repo = args.repo.resolve(strict=True)
    try:
        head = subprocess.run(["git", "rev-parse", "--verify", "HEAD"],
                              cwd=repo, capture_output=True, text=True,
                              check=True, timeout=5).stdout.strip()
        pin = (repo / "source/openwrt-source-commit.txt").read_text().strip()
        if args.expected_head and head != args.expected_head:
            raise ValueError("checked-out source revision differs from CI")
        data = create_manifest(head, pin)
        if args.out.is_symlink():
            raise ValueError("refusing manifest symlink")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        print("VECI_EXACT_BUILD_MANIFEST=PASS")
        return 0
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        print(f"VECI_EXACT_BUILD_MANIFEST=FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
