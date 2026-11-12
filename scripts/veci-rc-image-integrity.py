#!/usr/bin/env python3
"""Offline integrity attestation for a staged WE5927 firmware candidate.

Read-only. Does not invoke sysupgrade, write firmware, access a router, or
infer that the image is signed. Successful integrity is NEVER flash approval.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

BOARD = "zbtlink,zbt-we5927"
TARGET = "ramips/mt76x8"
VERSION = "25.12.5"
MTD_FIRMWARE_BYTES = 0x7A0000
MIN_IMAGE_BYTES = 256 * 1024


def check_file(path, name):
    if path.is_symlink() or not path.is_file():
        raise ValueError(name + "_missing_or_symlink")
    return path.read_bytes()


def attest(image: Path, metadata: Path, rootfs: Path, source_lte: Path,
           max_bytes: int = MTD_FIRMWARE_BYTES):
    problems = []
    sha = None
    size = None

    try:
        if image.is_symlink() or not image.is_file():
            raise ValueError("image_missing_or_symlink")
        size = image.stat().st_size
        if size < MIN_IMAGE_BYTES:
            problems.append("image_unreasonably_small")
        if size > max_bytes:
            problems.append("firmware_partition_exceeded")
        digest = hashlib.sha256()
        with image.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        sha = digest.hexdigest()
    except (ValueError, OSError) as e:
        problems.append("image_unreadable:" + str(e))

    try:
        data = json.loads(check_file(metadata, "metadata").decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("metadata_not_object")
        supported = data.get("supported_devices")
        if not isinstance(supported, list) or BOARD not in supported:
            problems.append("unsupported_board")
        ver = data.get("version")
        if not isinstance(ver, dict):
            problems.append("metadata_version_missing")
        else:
            if ver.get("target") != TARGET:
                problems.append("wrong_target")
            if ver.get("version") != VERSION:
                problems.append("wrong_openwrt_version")
            if ver.get("board") != "zbtlink_zbt-we5927":
                problems.append("wrong_board_profile")
    except (ValueError, UnicodeError, OSError) as e:
        problems.append("metadata_invalid:" + str(e))

    if rootfs.is_symlink() or not rootfs.is_dir():
        problems.append("rootfs_missing_or_symlink")
    else:
        try:
            wanted = check_file(source_lte, "pinned_lte_source")
            installed = check_file(rootfs / "usr/sbin/we5927-lte", "installed_lte")
            if wanted != installed:
                problems.append("stale_lte_source")
            for marker in (b"manual_reconnect() {", b"&& radio_or_link_lost; then"):
                if marker not in installed:
                    problems.append("lte_recovery_guard_missing")
                    break
        except (ValueError, OSError) as e:
            problems.append("lte_source_check_failed:" + str(e))
        try:
            guardian = check_file(rootfs / "usr/sbin/veci-wifi-guardian", "installed_guardian")
            if b"auto_recover=0" not in guardian or b"beacon_verified=0" not in guardian:
                problems.append("guardian_not_observe_only")
            # Active command lines must not reload/reset Wi-Fi.
            commands = b"\n".join(
                line for line in guardian.splitlines()
                if line.strip() and not line.lstrip().startswith(b"#")
            )
            if re.search(rb"(?m)(?:^|[;&|\s])wifi\s+(?:up|down|reload)\b", commands):
                problems.append("guardian_contains_disruptive_wifi_command")
        except (ValueError, OSError) as e:
            problems.append("guardian_check_failed:" + str(e))

    checks = {
        "image_size_bytes": size,
        "firmware_mtd_max_bytes": max_bytes,
        "sha256": sha,
        "board": BOARD,
        "source_version": VERSION,
        "build_integrity_pass": not problems,
        "blockers": sorted(set(problems)),
        "veci_native_spa_present": bool(
            (rootfs / "www/veci/index.html").is_file()
        ) if rootfs.is_dir() else False,
        # Image signature, hardware compatibility and recovery are independent
        # release requirements and are deliberately not inferred from this tool.
        "image_signature_verified": False,
        "hardware_uat_verified": False,
        "rollback_verified": False,
        "production_flash_authorized": False,
    }
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--rootfs", type=Path, required=True)
    parser.add_argument("--source-lte", type=Path, required=True)
    args = parser.parse_args()
    result = attest(args.image, args.metadata, args.rootfs, args.source_lte)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["build_integrity_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
