#!/usr/bin/env python3
"""Fail-closed offline WE5927 firmware verification; NEVER flashes hardware.

Use from a trusted Linux maintenance workstation with the *existing router's*
verified firmware-signing public keys. An arbitrary CI/build key is not trust.
"""
import argparse
import hashlib
import json
import pathlib
import re
import stat
import subprocess
import sys
import tempfile

BOARD = "zbtlink,zbt-we5927"
TARGET = "ramips/mt76x8"
VERSION = "25.12.5"
MTD_MAX = 0x7A0000


class GateError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise GateError(message)


def check_image_file(image, expected_sha):
    require(re.fullmatch(r"[0-9a-f]{64}", expected_sha) is not None,
            "expected SHA-256 must be 64 lowercase hex characters")
    require(not image.is_symlink(), "refusing symlink image")
    try:
        info = image.stat()
    except OSError as error:
        raise GateError("image unavailable: " + str(error)) from error
    require(stat.S_ISREG(info.st_mode), "image is not a regular file")
    require(0 < info.st_size <= MTD_MAX,
            f"firmware MTD overflow or empty image: {info.st_size} > {MTD_MAX}")
    digest = hashlib.sha256()
    with image.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            digest.update(chunk)
    require(digest.hexdigest() == expected_sha, "image SHA-256 mismatch")
    return info.st_size


def check_metadata(metadata):
    require(isinstance(metadata, dict), "invalid image metadata JSON")
    devices = metadata.get("supported_devices", [])
    require(isinstance(devices, list) and BOARD in devices,
            "image board metadata mismatch")
    version = metadata.get("version", {})
    require(isinstance(version, dict), "invalid firmware version object")
    require(version.get("target") == TARGET, "image target mismatch")
    require(version.get("version") == VERSION, "OpenWrt release mismatch")


def verify(image, sha, trust_dir, fwtool="fwtool", ucert="ucert"):
    image = pathlib.Path(image)
    trust_dir = pathlib.Path(trust_dir)
    size = check_image_file(image, sha)
    require(trust_dir.is_dir() and not trust_dir.is_symlink(),
            "verified firmware public-key directory unavailable")
    keys = [p for p in trust_dir.iterdir() if p.is_file() and not p.is_symlink()]
    require(bool(keys), "firmware trust directory contains no keys")
    with tempfile.TemporaryDirectory(prefix="veci-release-") as temporary:
        meta = pathlib.Path(temporary) / "metadata.json"
        cert = pathlib.Path(temporary) / "signature.ucert"
        try:
            extract_meta = subprocess.run(
                [fwtool, "-i", str(meta), str(image)],
                capture_output=True, check=False, timeout=20)
            require(extract_meta.returncode == 0 and meta.is_file() and
                    meta.stat().st_size > 0, "missing/invalid image metadata")
            try:
                check_metadata(json.loads(meta.read_text()))
            except (ValueError, UnicodeDecodeError) as error:
                raise GateError("corrupt image metadata JSON") from error

            extract_cert = subprocess.run(
                [fwtool, "-s", str(cert), str(image)],
                capture_output=True, check=False, timeout=20)
            require(extract_cert.returncode == 0 and cert.is_file() and
                    cert.stat().st_size > 0, "missing firmware ucert signature")

            # Match OpenWrt fwtool.sh: verify original unsigned image bytes
            # against the appended certificate using existing trusted keys.
            with subprocess.Popen(
                [fwtool, "-T", "-s", "/dev/null", str(image)],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as unsigned:
                verify_sig = subprocess.run(
                    [ucert, "-V", "-m", "-", "-c", str(cert), "-P", str(trust_dir)],
                    stdin=unsigned.stdout, capture_output=True,
                    check=False, timeout=30)
                unsigned.stdout.close()
                extract_exit = unsigned.wait(timeout=20)
            require(extract_exit == 0 and verify_sig.returncode == 0,
                    "firmware signature failed trusted-key verification")
        except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired) as error:
            raise GateError("missing verification tool or verifier failed: " +
                            str(error)) from error
    return {
        "board": BOARD, "target": TARGET, "version": VERSION,
        "image_bytes": size, "image_sha256": sha,
        "metadata": "PASS", "signature_against_existing_keys": "PASS",
        "offline_release_gate": "PASS",
        "router_sysupgrade_test": "PENDING",
        "router_live_uat": "PENDING",
        "recovery_and_72h": "PENDING",
        "flash_permission": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--sha256", required=True,
                        help="SHA-256 of FINAL SIGNED image, not unsigned build")
    parser.add_argument("--trusted-key-dir", required=True,
                        help="independently VERIFIED public keys from existing router")
    parser.add_argument("--fwtool", default="fwtool")
    parser.add_argument("--ucert", default="ucert")
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.image, args.sha256,
                                args.trusted_key_dir, args.fwtool,
                                args.ucert), indent=2, sort_keys=True))
    except (GateError, OSError) as error:
        print("OFFLINE_IMAGE_GATE=FAIL: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
