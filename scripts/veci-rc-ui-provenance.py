#!/usr/bin/env python3
"""Read-only static VeCI UI source provenance check.

Use against previously captured *current* production /www/veci and a
candidate image's /www/veci. Never read router private UCI/config/keys.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys

SUFFIXES = {".html", ".js", ".css", ".json", ".svg", ".png", ".webp"}
MAX_FILES = 256
MAX_FILE_BYTES = 1024 * 1024


def inventory(root):
    if root.is_symlink() or not root.is_dir():
        raise ValueError("veci_root_invalid")
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("veci_ui_symlink_disallowed")
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if len(PurePosixPath(rel).parts) > 8 or ".." in PurePosixPath(rel).parts:
            raise ValueError("ui_path_invalid")
        if path.suffix.lower() not in SUFFIXES:
            raise ValueError("unknown_ui_asset_type:" + rel)
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("oversized_ui_asset:" + rel)
        if len(result) >= MAX_FILES:
            raise ValueError("too_many_ui_assets")
        result[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    if "index.html" not in result or "js/app.js" not in result:
        raise ValueError("veci_core_entrypoints_missing")
    return {"schema_version": 1, "files": result}


def compare(approved, candidate):
    if approved.get("schema_version") != 1 or candidate.get("schema_version") != 1:
        raise ValueError("incompatible_manifest_version")
    old, new = approved["files"], candidate["files"]
    for obj in (old, new):
        if not isinstance(obj, dict) or any(
            not isinstance(k, str) or not isinstance(v, str) or
            not v or not (len(v) == 64 and all(c in "0123456789abcdef" for c in v))
            for k, v in obj.items()
        ):
            raise ValueError("invalid_manifest")
    return {
        "same_source": old == new,
        "missing": sorted(set(old) - set(new)),
        "unapproved_new": sorted(set(new) - set(old)),
        "changed": sorted(k for k in old.keys() & new.keys() if old[k] != new[k]),
        "current_ui_verified": old == new,
        "production_flash_authorized": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ui-root", type=Path, required=True)
    parser.add_argument("--approved-manifest", type=Path,
                        help="hashed manifest captured from CURRENT production UI")
    args = parser.parse_args()
    try:
        now = inventory(args.ui_root)
        if args.approved_manifest:
            base = json.loads(args.approved_manifest.read_text(encoding="utf-8"))
            result = compare(base, now)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result["same_source"] else 1
        print(json.dumps(now, indent=2, sort_keys=True))
        # Inventory mode is not a production acceptance claim.
        return 0
    except (ValueError, OSError, KeyError, TypeError) as e:
        print(json.dumps({"current_ui_verified": False, "error": str(e),
                          "production_flash_authorized": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
