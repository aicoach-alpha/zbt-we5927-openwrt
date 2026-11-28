"""Validate resolved OEM target config; no compilation or flash permission."""
import sys
from pathlib import Path

REQUIRED = {
    "busybox", "firewall4", "nftables-json", "dnsmasq", "ip-tiny",
    "coreutils-timeout", "flock", "curl", "ca-bundle", "iw", "swconfig",
    "ppp", "ppp-mod-pppoe", "pppoe-discovery", "rpcd", "jsonfilter",
    "uhttpd", "uhttpd-mod-ubus", "libubox", "fwtool", "ucert",
    "veci-v2-runtime", "veci-v2-sms", "veci-v2-ipv6",
    "veci-v2-package-manager", "veci-wifi-guardian", "we5927-lte",
    "oem-updated-ui-dev",
}
FORBIDDEN = {"veci-v2-ui","veci-default-ui","veci-cellular-we5927",
             "veci-app-guest","veci-app-voucher","uspot","uspot-www"}
TARGET = {"CONFIG_TARGET_ramips", "CONFIG_TARGET_ramips_mt76x8",
          "CONFIG_TARGET_ramips_mt76x8_DEVICE_zbtlink_zbt-we5927"}
def check(config):
    # Last assignment is not a substitute for Kconfig resolution.
    entries={}
    for line in config.splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key,value=line.split("=",1)
            if key in entries and entries[key]!=value:
                raise ValueError("conflicting assignment: "+key)
            entries[key]=value
    missing=sorted(k for k in TARGET|{"CONFIG_PACKAGE_"+p for p in REQUIRED} if entries.get(k)!="y")
    forbidden=sorted(k for k,v in entries.items() if v=="y" and k.startswith("CONFIG_PACKAGE_") and (k[15:] in FORBIDDEN or k[15:]=="luci" or k[15:].startswith("luci-")))
    if entries.get("CONFIG_BUSYBOX_CUSTOM")=="y":
        missing.extend("CONFIG_BUSYBOX_CONFIG_"+a for a in ("PING","PING6","NSLOOKUP","TRACEROUTE","TRACEROUTE6") if entries.get("CONFIG_BUSYBOX_CONFIG_"+a)!="y")
    return missing,forbidden
if __name__=="__main__":
    missing,forbidden=check(Path(sys.argv[1]).read_text())
    if missing or forbidden:
        raise SystemExit(f"OEM_CONFIG_BLOCKED missing={missing} forbidden={forbidden}")
    print("OEM_RESOLVED_CONFIG=PASS; SOURCE_ONLY=YES; FLASH_ALLOWED=NO")
