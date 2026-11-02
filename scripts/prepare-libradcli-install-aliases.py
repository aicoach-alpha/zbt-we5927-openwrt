#!/usr/bin/env python3
"""Fail-closed incremental OpenWrt build repair. Never accesses a router."""
import json
import pathlib
import subprocess
import sys

ALIAS_DIR = pathlib.Path(
    "openwrt/build_dir/target-mipsel_24kc_musl/radcli-1.3.0/"
    "ipkg-install/usr/lib"
)
ALIASES = ("libfreeradius-client.so", "libradiusclient-ng.so")
TARGET = "libradcli.so"


def clear_known_aliases(root):
    """Remove only idempotency-conflicting aliases after validating both."""
    parent = pathlib.Path(root) / ALIAS_DIR
    if not parent.is_dir() or parent.is_symlink():
        return []
    canonical = parent.resolve()
    if canonical != parent.absolute():
        raise ValueError("radcli staging directory is redirected")
    if not (parent / TARGET).exists():
        raise ValueError("radcli library target is missing")
    selected = []
    for name in ALIASES:
        candidate = parent / name
        if candidate.is_symlink():
            if str(candidate.readlink()) != TARGET:
                raise ValueError("unexpected radcli alias target: " + name)
            selected.append(candidate)
        elif candidate.exists():
            raise ValueError("unexpected regular radcli alias file: " + name)
    for item in selected:
        item.unlink()
    return [item.name for item in selected]


def main():
    if len(sys.argv) != 2:
        print("usage: prepare-libradcli-install-aliases.py <external-build-root>", file=sys.stderr)
        return 2
    root = pathlib.Path(sys.argv[1])
    archive = pathlib.Path("/mnt/data/andre-maintenance-archives")
    if (not root.is_dir() or root.is_symlink() or
            root.resolve().parent != archive.resolve() or
            not root.name.startswith("veci-cafe-build-") or
            not (root / "openwrt/rules.mk").is_file()):
        print("STOP: invalid external OpenWrt staging root", file=sys.stderr)
        return 3
    source = pathlib.Path(__file__).resolve().parents[1]
    expected = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True, timeout=10
    ).strip()
    meta = json.loads(
        (root / "openwrt/package/veci-default-ui/files/etc/veci-release.json").read_text()
    )
    if meta.get("build_id") != expected:
        print("STOP: staged source does not match tested firmware source", file=sys.stderr)
        return 4
    if subprocess.check_output(
        ["docker", "ps", "-q", "--filter", "name=^/veci-cafe-builder$"],
        text=True, timeout=15
    ).strip():
        print("STOP: concurrent builder running", file=sys.stderr)
        return 5
    try:
        removed = clear_known_aliases(root)
    except ValueError as error:
        print("STOP: " + str(error), file=sys.stderr)
        return 6
    print("LIBRADCLI_IDEMPOTENCY_PREFLIGHT=PASS")
    print("REMOVED_ALIAS_COUNT=" + str(len(removed)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
