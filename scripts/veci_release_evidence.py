#!/usr/bin/env python3
"""Attest exact RC1 CI checkout and reviewed head without signing or flashing."""
import argparse
import json
from pathlib import Path
import re
import subprocess

HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def make_report(meta, pin, size, maximum, image_sha, build_sha,
                reviewed_head, reviewed_base, event, parents,
                export_requested=False, ref=""):
    for field, value in (("build sha", build_sha),
                         ("reviewed head", reviewed_head),
                         ("OpenWrt pin", pin)):
        require(isinstance(value, str) and HEX40.fullmatch(value), "invalid " + field)
    require(isinstance(image_sha, str) and HEX64.fullmatch(image_sha),
            "invalid image SHA-256")
    require(type(size) is int and type(maximum) is int and 0 < size <= maximum == 7995392,
            "invalid firmware MTD fit")
    require(meta.get("version", {}).get("target") == "ramips/mt76x8" and
            meta["version"].get("version") == "25.12.5" and
            "zbtlink,zbt-we5927" in meta.get("supported_devices", []),
            "wrong board or OpenWrt version")
    if event == "pull_request":
        require(isinstance(reviewed_base, str) and HEX40.fullmatch(reviewed_base),
                "missing reviewed base")
        require(len(parents) == 2 and parents[0] == reviewed_base and
                parents[1] == reviewed_head,
                "CI merge commit does not contain reviewed head/base")
        require(not export_requested, "PR CI cannot export unsigned candidate")
    elif event == "workflow_dispatch":
        require(reviewed_head == build_sha and not reviewed_base,
                "manual checkout mismatches source ref")
        require(not export_requested or
                ref == "refs/heads/integration/veci-feature-complete-20261114",
                "unsigned export requires reviewed RC branch")
    else:
        raise ValueError("unsupported build event")
    return {
        "schema": "veci.we5927.rc1.ci-evidence.v2",
        "github_build_sha": build_sha,
        "github_event_name": event,
        "github_ref": ref,
        "reviewed_head_sha": reviewed_head,
        "reviewed_base_sha": reviewed_base or None,
        "openwrt_source_sha": pin,
        "board": "zbtlink,zbt-we5927",
        "target": "ramips/mt76x8",
        "openwrt_version": "25.12.5",
        "image_sha256": image_sha,
        "image_bytes": size,
        "firmware_mtd_bytes": maximum,
        "remaining_bytes": maximum - size,
        "checks": {
            "complete_source_build": "pass",
            "board_metadata": "pass",
            "image_partition_fit": "pass",
            "reviewed_checkout_provenance": "pass",
            "lte_and_guardian_source_installed": "pass",
            "builtin_veci_core_rpc_default_ui": "pass",
            "veci_web_cellular_sms_catalog_update_source": "pass",
            "guest_voucher_optional_not_bundled": "pass",
            "luci_fallback_retained": "pass",
            "release_signing_and_trust_anchor": "not_verified",
            "existing_veci_spa_parity": "not_verified",
            "physical_router_uat": "not_run",
            "rollback_recovery": "not_verified",
            "long_window_72h": "not_run"
        },
        "unsigned_candidate_export_requested": bool(export_requested),
        "firmware_binary_uploaded": False,  # snapshot taken before artifact upload
        "flash_permission": False,
    }


def main():
    parser = argparse.ArgumentParser()
    for name in ("metadata", "pin", "out", "sha", "build-sha",
                 "reviewed-head", "reviewed-base", "event", "repo", "ref",
                 "requested-unsigned-export"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--size", type=int, required=True)
    parser.add_argument("--max-size", type=int, required=True)
    args = parser.parse_args()
    require(args.requested_unsigned_export in ("true", "false"),
            "bad unsigned export flag")
    require(bool(HEX40.fullmatch(args.build_sha)), "invalid build sha")
    repo = Path(args.repo)
    actual = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                            capture_output=True, text=True, check=True, timeout=5).stdout.strip()
    require(actual == args.build_sha, "checkout HEAD does not match GITHUB_SHA")
    raw = subprocess.run(["git", "cat-file", "-p", "HEAD"], cwd=repo,
                         capture_output=True, text=True, check=True, timeout=5).stdout
    parents = [line.split(" ", 1)[1] for line in raw.splitlines()
               if line.startswith("parent ")]
    report = make_report(
        json.loads(Path(args.metadata).read_text()), Path(args.pin).read_text().strip(),
        args.size, args.max_size, args.sha, args.build_sha, args.reviewed_head,
        args.reviewed_base, args.event, parents,
        args.requested_unsigned_export == "true", args.ref)
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("REVIEWED_SOURCE_AND_NONFLASHABLE_CI_EVIDENCE=PASS")


if __name__ == "__main__":
    main()
