#!/usr/bin/env python3
"""Audit actual unpacked SquashFS; a green source/build does not prove features.

Never flashes or changes a router. A passing static inventory still requires
real hardware/functional UAT and upgrade compatibility before production use.
"""
import argparse
import json
from pathlib import Path
import re

PAGES = ("home", "internet", "wifi", "devices", "cellular", "hotspot",
         "security", "network", "system", "updates", "apps")


def inventory(root):
    root = Path(root)
    exists = lambda path: (root / path).is_file()
    release = root / "etc/veci-release.json"
    build_id = None
    if release.is_file():
        try:
            info = json.loads(release.read_text(encoding="utf-8"))
            if (isinstance(info, dict)
                and info.get("board") == "zbtlink,zbt-we5927"
                and isinstance(info.get("build_id"), str)
                and re.fullmatch(r"[a-f0-9]{40}", info["build_id"])):
                build_id = info["build_id"]
        except (ValueError, UnicodeError, OSError):
            pass
    home = root / "www/index.html"
    native_home = home.is_file() and 'url=/veci/' in home.read_text(errors="replace")
    pages = [name for name in PAGES if
             exists(f"www/veci/js/pages/{name}.js")]
    checks = {
        "veci_native_home": native_home,
        "veci_native_pages": len(pages) == len(PAGES),
        "veci_core_rpc": exists("usr/libexec/rpcd/veci"),
        "release_identity": bool(build_id),
        "lte_recovery": exists("usr/sbin/we5927-lte") and exists("etc/init.d/we5927-lte"),
        "wifi_guardian": exists("usr/sbin/veci-wifi-guardian"),
        "sms_center": (exists("usr/libexec/rpcd/veci.sms")
                       and exists("usr/libexec/veci-sms-send-one")
                       and exists("usr/libexec/veci-sms-drafts")),
        "guest_portal_runtime": (exists("usr/libexec/rpcd/veci.app.guest")
                                 and exists("www/veci-apps/guest.js")),
        "voucher_runtime": (exists("usr/libexec/rpcd/veci.app.voucher")
                            and exists("www/veci-apps/voucher.js")),
        "operator_quota_backend": exists("usr/libexec/rpcd/veci.quota"),
         "native_data_meter": (exists("usr/libexec/rpcd/veci.meter")
                               and exists("www/veci/data-meter.html")
                               and exists("www/veci/data-meter.js")),
        "firmware_update_agent": exists("usr/sbin/veci-update-agent"),
        "app_catalog": exists("usr/libexec/rpcd/veci.apps"),
    }
    missing = sorted(k for k, v in checks.items() if not v)
    return {
        "scope": "offline_filesystem_only",
        "board": "zbtlink,zbt-we5927",
        "build_id": build_id,
        "veci_page_count": len(pages),
        "checks": checks,
        "missing": missing,
        "static_feature_parity": "PASS" if not missing else "FAIL",
        "physical_uat": "NOT_VERIFIED",
        "firmware_signature": "NOT_VERIFIED",
        "sysupgrade_test": "NOT_VERIFIED",
        "production_flash_permission": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rootfs", type=Path, required=True)
    parser.add_argument("--require-all", action="store_true")
    args = parser.parse_args()
    result = inventory(args.rootfs)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if args.require_all and result["missing"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
