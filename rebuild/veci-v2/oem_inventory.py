#!/usr/bin/env python3
"""Extract only a non-sensitive feature inventory from the *exact* OEM image.
Never copy/execute vendor binaries or vendor account/secret configuration.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

MODEL = "ZBT-WE5927-DSIM"
DISPLAY = "WE2825-2SIM"
SHA = "80529b8e9c31d686eb7f63a1517d6dbcf781f26cb4aceb7b8b1ff27c2d51d1f9"
SOURCE = ("https://cdn.shopify.com/s/files/1/0760/0416/3873/files/"
          "WE2825-2SIM_V26.03.04_V26.08.09.bin?v=1786953217")

# Only public, non-secret, exactly known fields.
WHITELIST = ("device_model", "device_model_displayname", "device_version",
             "version_date", "doggpio", "dogtype")
MENU_GROUPS = ("config", "net", "wifi", "adv", "srv", "mgnt", "tool")


def parse_uci_safe(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    parsed = {}
    for line in text.splitlines():
        match = re.fullmatch(r"\s*option\s+([a-z0-9_]+)\s+'([^']*)'\s*", line)
        if match and match.group(1) in WHITELIST:
            parsed[match.group(1)] = match.group(2)
    return parsed


def inventory(root, firmware):
    root = Path(root)
    version = root.joinpath("etc/openwrt_release").read_text(encoding="utf-8")
    if "DISTRIB_ID='LEDE'" not in version or "DISTRIB_TARGET='ramips/mt7628'" not in version:
        raise ValueError("not the validated vendor LEDE ramips/mt7628 filesystem")
    id_fields = parse_uci_safe(root / "etc/config/anyversion")
    if id_fields.get("device_model") != MODEL or id_fields.get("device_model_displayname") != DISPLAY:
        raise ValueError("different OEM board; refusing inventory")
    if id_fields.get("device_version") != "26.08.09":
        raise ValueError("different vendor release")
    menu = json.loads((root / "www/menu_conf1.json").read_text(encoding="utf-8"))
    if not isinstance(menu, dict) or not set(MENU_GROUPS).issubset(menu):
        raise ValueError("incomplete OEM feature menu")
    groups = {}
    for category in MENU_GROUPS:
        if not isinstance(menu[category], dict):
            raise ValueError("invalid menu")
        flags = {}
        for name, enabled in sorted(menu[category].items()):
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,59}", name):
                raise ValueError("unsafe menu key")
            if type(enabled) is not int or enabled not in (0, 1):
                raise ValueError("invalid menu availability flag")
            flags[name] = bool(enabled)
        groups[category] = flags
    binary = Path(firmware)
    if hashlib.sha256(binary.read_bytes()).hexdigest() != SHA:
        raise ValueError("OEM reference binary hash mismatch")
    return {
        "schema": "veci.oem-inventory.v1",
        "evidence": "EXTRACTED_OEM_REFERENCE_NOT_ROUTER_FLASH_APPROVAL",
        "source_url": SOURCE,
        "source_sha256": SHA,
        "source_image_bytes": binary.stat().st_size,
        "vendor_model": id_fields["device_model"],
        "vendor_display_model": id_fields["device_model_displayname"],
        "vendor_release": id_fields["device_version"],
        "vendor_watchdog_gpio_source": int(id_fields.get("doggpio", "-1")),
        "vendor_watchdog_type_source": int(id_fields.get("dogtype", "-1")),
        "vendor_os": "LEDE ramips/mt7628 Linux 4.4.61",
        "menu_flags": groups,
        "vendor_bundled_driver_filenames": [
            x for x in ("mt7628.ko", "mt76x2e.ko")
            if (root / "lib/modules/4.4.61" / x).is_file()
        ],
        "migration_note": (
            "menu true means visible in OEM, not proof of live feature function; "
            "menu false means disabled, not guaranteed hardware support"
        )
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rootfs", type=Path, required=True)
    parser.add_argument("--firmware", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = inventory(args.rootfs, args.firmware)
    if args.output.is_symlink():
        raise ValueError("output symlink refused")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    print("EXACT_OEM_SAFE_FEATURE_INVENTORY=PASS")


if __name__ == "__main__":
    main()
