#!/usr/bin/env python3
"""Fail-closed source/build gate before removing LuCI from VeCI firmware.

Use --root to point to a staged firmware rootfs (not a live router).
This is a conservative migration gate, NOT a claim of UI feature parity.
"""
import argparse
import json
import pathlib
import re
import sys

# Services VeCI must retain regardless of whether their names contain "luci".
REQUIRED_PATHS = (
    "usr/sbin/uhttpd",
    "sbin/ubusd",
    "sbin/uci",
    "usr/sbin/rpcd",
)
# All are either paths in the staged rootfs or exact installed-package names.
LUCIPKG = re.compile(r"^luci(?:$|[-_])")
LUCIPATH = re.compile(r"(^|/)luci(?:/|-static/|-app-)")
LEGACY_UI_REFERENCE = re.compile(r"(?:/cgi-bin/luci|/luci-static/|luci-proto-wireguard)")

def evaluate(root, packages, required=REQUIRED_PATHS):
    findings = []
    if not root.is_dir():
        return ["staged_rootfs_missing"]
    for rel in required:
        if not (root / rel).exists():
            findings.append("required_runtime_missing:" + rel)
    for name in packages:
        if LUCIPKG.match(name):
            findings.append("luci_package_present:" + name)
    for location in ("www/luci-static", "usr/share/luci", "usr/lib/lua/luci"):
        if (root / location).exists():
            findings.append("legacy_ui_path_present:" + location)
    # Search only text source/assets. Never read secrets, /etc/config or binary blobs.
    for rel in ("www", "usr/share/veci"):
        base = root / rel
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.is_symlink() or path.stat().st_size > 512_000:
                continue
            if path.suffix not in (".js", ".css", ".html", ".json"):
                continue
            data = path.read_text(encoding="utf-8", errors="replace")
            if LEGACY_UI_REFERENCE.search(data):
                findings.append("legacy_ui_reference:" + str(path.relative_to(root)))
    return sorted(set(findings))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=pathlib.Path, required=True,
                        help="staged rootfs; NEVER run against the active router")
    parser.add_argument("--packages", type=pathlib.Path, required=True,
                        help="newline-separated exact package names from image build")
    args = parser.parse_args()
    if not args.packages.is_file():
        print(json.dumps({"ok": False, "findings": ["package_manifest_missing"]}))
        return 2
    names = [line.strip().split()[0] for line in
             args.packages.read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    findings = evaluate(args.root.resolve(), names)
    print(json.dumps({"ok": not findings, "findings": findings}, indent=2))
    return 1 if findings else 0

if __name__ == "__main__":
    sys.exit(main())
