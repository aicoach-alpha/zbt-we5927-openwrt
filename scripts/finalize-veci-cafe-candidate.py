#!/usr/bin/env python3
"""Generate a local, non-flashable candidate artifact with source/manifest evidence.

Do not publish, deploy, install, or contact the live router. Output directory
must be a new empty path below the external NAS build-cache tree.
"""
import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

TARGET = "ramips/mt76x8"
BOARD = "zbtlink_zbt-we5927"
PINNED_OPENWRT = "c740570351512e4400369b3c2aff49741f65580e"


def fail(message):
    raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def exact_one(paths, meaning):
    found = sorted(p for p in paths if p.is_file() and not p.is_symlink())
    if len(found) != 1:
        fail("Expected exactly one %s, found %d" % (meaning, len(found)))
    return found[0]


def finalize(firmware, build_tree, out):
    firmware = pathlib.Path(firmware).resolve()
    build_tree = pathlib.Path(build_tree).resolve()
    out = pathlib.Path(out).absolute()
    if out.is_symlink() or out.exists():
        fail("Output already exists; refusing to overwrite or follow a symlink")
    archive = pathlib.Path("/mnt/data/andre-maintenance-archives").resolve()
    # Check resolved parents too: a symlinked parent must not redirect output
    # onto the NAS root disk or into an unrelated service's directory.
    try:
        out.parent.resolve().relative_to(archive)
    except ValueError:
        fail("Only an external maintenance archive may receive a candidate")
    if build_tree.is_symlink() or not (build_tree / "rules.mk").is_file():
        fail("OpenWrt build tree missing")
    actual_openwrt = subprocess.check_output(
        ["git", "-C", str(build_tree), "rev-parse", "HEAD"], text=True, timeout=10
    ).strip()
    if actual_openwrt != PINNED_OPENWRT:
        fail("OpenWrt source commit mismatch")
    build_metadata = build_tree / "package/veci-default-ui/files/etc/veci-release.json"
    meta = json.loads(build_metadata.read_text())
    source_commit = meta.get("build_id", "")
    if (not isinstance(source_commit, str) or len(source_commit) != 40
            or any(c not in "0123456789abcdef" for c in source_commit)):
        fail("Invalid source commit in staged firmware metadata")
    # A safe long-running build can finish AFTER additional tested changes
    # have landed. Check against its original immutable Git object rather
    # than the repository's moving HEAD.
    subprocess.run(
        ["git", "-C", str(firmware), "cat-file", "-e", source_commit + "^{commit}"],
        capture_output=True, text=True, check=True, timeout=10
    )
    head = subprocess.check_output(
        ["git", "-C", str(firmware), "rev-parse", "HEAD"], text=True, timeout=10
    ).strip()
    subprocess.run(
        ["git", "-C", str(firmware), "merge-base", "--is-ancestor", source_commit, head],
        capture_output=True, check=True, timeout=10
    )
    expected_core = subprocess.check_output(
        ["git", "-C", str(firmware), "show", source_commit + ":source/veci.commit"],
        text=True, timeout=10
    ).strip()
    if (meta.get("veci_commit") != expected_core
            or meta.get("openwrt_commit") != PINNED_OPENWRT
            or meta.get("edition") != "general"):
        fail("Staged firmware metadata is stale or has mismatched source pins")
    target_dir = build_tree / "bin/targets/ramips/mt76x8"
    if not target_dir.is_dir():
        fail("No target output folder: firmware build unfinished")
    image = exact_one(target_dir.glob("*zbt-we5927*sysupgrade.bin"), "WE5927 image")
    manifest = exact_one(target_dir.glob("*zbt-we5927*.manifest"), "WE5927 manifest")
    fwtool = build_tree / "staging_dir/host/bin/fwtool"
    if not fwtool.is_file() or not fwtool.stat().st_mode & 0o111:
        fail("Build-matched host fwtool missing")
    verifier = firmware / "scripts/verify-veci-general-cafe-image.sh"
    validated = subprocess.run(
        ["sh", str(verifier), str(image), str(manifest), str(fwtool)],
        text=True, capture_output=True, timeout=80
    )
    if validated.returncode:
        fail("Image verification failed: " + (validated.stderr + validated.stdout)[-900:])
    if "FLASH_DECISION=NO_GO_UNTIL_HARDWARE_RECOVERY_AND_UAT" not in validated.stdout:
        fail("Verifier did not explicitly retain physical-flash NO_GO")
    image_sha = sha(image)
    manifest_sha = sha(manifest)
    # Never copy artifacts to the public web directory or GitHub release.
    out.mkdir(parents=True, mode=0o700)
    try:
        for origin in (image, manifest):
            shutil.copyfile(origin, out / origin.name)
        report = {
            "status": "CANDIDATE_OFFLINE_VALIDATED_NOT_FLASH_APPROVED",
            "flash_decision": "NO_GO_UNTIL_HARDWARE_RECOVERY_AND_UAT",
            "source_commit": source_commit,
            "core_commit": expected_core,
            "openwrt_commit": actual_openwrt,
            "board": BOARD,
            "target": TARGET,
            "image": {"name": image.name, "sha256": image_sha, "bytes": image.stat().st_size},
            "manifest": {"name": manifest.name, "sha256": manifest_sha},
            "verifier_output": validated.stdout.strip(),
            "hardware_uat": "NOT_TESTED",
            "signed_app_feed": "NOT_ATTESTED_BY_THIS_GATE",
            "router_deployment": "NOT_PERFORMED"
        }
        (out / "RELEASE-CANDIDATE.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n"
        )
        lines = [sha(out / name) + "  " + name for name in sorted(
            [image.name, manifest.name, "RELEASE-CANDIDATE.json"
        ])]
        (out / "SHA256SUMS").write_text("\n".join(lines) + "\n")
    except Exception:
        shutil.rmtree(out)
        raise
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--firmware", required=True)
    p.add_argument("--build-tree", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    try:
        report = finalize(args.firmware, args.build_tree, args.output)
    except (OSError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print("CANDIDATE_BLOCKED: " + str(e), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
