#!/usr/bin/env python3
"""Reject all new or changed LuCI user-facing code after VeCI-only policy.

Historical LuCI files are grandfathered only as unchanged legacy artifacts;
deleting them is permitted. Run on a clone containing the policy-baseline
commit. No network, firmware, filesystem mutation, or modem access.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

BASELINE = "7319404d54f5fa7b856fee48197f9bbabe99971c"


def is_luci_ui_path(path: str) -> bool:
    normalized = "/" + path.lower().strip("/") + "/"
    basename = Path(path.lower()).name
    return any(
        segment in normalized
        for segment in (
            "/luci-static/",
            "/share/luci/",
            "/luci/view/",
            "/luci/controller/",
        )
    ) or basename.startswith("luci-app-")


def changed_paths(base: str, head: str) -> list[tuple[str, str]]:
    out = subprocess.check_output(
        [
            "git", "diff", "--name-status", "--no-renames",
            "--no-ext-diff", "--diff-filter=ADMRT",
            f"{base}..{head}",
        ],
        text=True,
    )
    result = []
    for line in out.splitlines():
        chunks = line.split("\t")
        if len(chunks) != 2:
            raise RuntimeError("unexpected git diff format")
        result.append((chunks[0], chunks[1]))
    return result


def enforce(changes: list[tuple[str, str]]) -> list[str]:
    # M / A / T are disallowed. D means removing legacy LuCI UI.
    return [
        f"{status}: {path}"
        for status, path in changes
        if status != "D" and is_luci_ui_path(path)
    ]


def main() -> int:
    base = os.environ.get("VECI_POLICY_BASE", BASELINE)
    head = os.environ.get("VECI_POLICY_HEAD", "HEAD")
    subprocess.run(["git", "cat-file", "-e", f"{base}^{{commit}}"], check=True)
    if (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", base, head],
            check=False,
        ).returncode != 0
    ):
        print("VECI_ONLY_UI_POLICY=blocked: baseline not ancestor", file=sys.stderr)
        return 1

    violations = enforce(changed_paths(base, head))
    if violations:
        print("VECI_ONLY_UI_POLICY=FAIL")
        for violation in violations:
            print("LuCI UI development forbidden: " + violation)
        print("Implement the feature in a VeCI page/module instead.")
        return 1
    print("VECI_ONLY_UI_POLICY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
