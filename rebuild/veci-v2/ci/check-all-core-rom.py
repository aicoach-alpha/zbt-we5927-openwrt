#!/usr/bin/env python3
"""Require exact source-backed VeCI runtime assets inside extracted final SquashFS.

This runs AFTER building the one candidate image; it cannot authorize a flash,
sign images, infer hardware availability or replace a physical 72-hour test.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
CONTRACT=ROOT/"rebuild/veci-v2/contracts/veci-v2-rebuild-contract.json"
BASE="rebuild/veci-v2/packages"
RTL=BASE+"/veci-v2-runtime/"
UI=BASE+"/veci-v2-ui/files/www/"
SMS="source/veci-cellular-we5927/files/usr/libexec/"
IPV6=BASE+"/veci-v2-ipv6/files/"
WE="source/we5927-lte/files/"
GUARD="source/veci-wifi-guardian/"
PKG=BASE+"/veci-v2-package-manager/"

# Mapping is explicit: no "package installed" pass without a concrete
# exact source payload in the SquashFS image. Shared providers may serve
# several features; each feature must still have a distinct evidence entry.
FEATURES={
 "dashboard_status":[(RTL+"veci2-status","usr/libexec/rpcd/veci.v2")],
 "router_login_and_permissions":[(UI+"veci2/app.js","www/veci2/app.js")],
 "interface_wan_lan":[(RTL+"veci2-interfaces","usr/libexec/rpcd/veci.v2.interfaces")],
 "dhcp_dns_static_leases":[(RTL+"veci2-static-leases","usr/libexec/rpcd/veci.v2.dhcp"),
                           (RTL+"veci2-dns","usr/libexec/rpcd/veci.v2.dns")],
 "ipv6_ra_dhcpv6":[(IPV6+"usr/libexec/rpcd/veci2-ra","usr/libexec/rpcd/veci.v2.ra")],
 "firewall_zones_nat":[(RTL+"veci2-firewall","usr/libexec/rpcd/veci.v2.firewall")],
 "port_forward_dmz":[(RTL+"veci2-firewall","usr/libexec/rpcd/veci.v2.firewall")],
 "static_routes_policy":[(RTL+"veci2-routes","usr/libexec/rpcd/veci.v2.routes")],
 "wifi_ap_2g":[(RTL+"veci2-wifi","usr/libexec/rpcd/veci.v2.wifi")],
 "wifi_survey_channel":[(RTL+"veci2-wifi-controls","usr/libexec/veci2-wifi-controls")],
 "wifi_clients_access_control":[(RTL+"veci2-wifi-controls","usr/libexec/veci2-wifi-controls")],
 "ethernet_port_status":[(RTL+"veci2-status","usr/libexec/rpcd/veci.v2")],
 "lte_rndis_data":[(WE+"usr/sbin/we5927-lte","usr/sbin/we5927-lte")],
 "lte_dual_sim_manual":[(RTL+"veci2-sim-manual","usr/libexec/rpcd/veci.v2.sim")],
 "lte_apn_pin_puk":[(RTL+"veci2-lte-policy","usr/libexec/rpcd/veci.v2.lte"),
                    (RTL+"veci2-sim-lock","usr/libexec/rpcd/veci.v2.simlock")],
 "sms_inbox":[(SMS+"rpcd/veci.sms","usr/libexec/rpcd/veci.sms")],
 "sms_sent_and_drafts":[(SMS+"veci-sms-sent-history","usr/libexec/veci-sms-sent-history"),
                        (SMS+"veci-sms-drafts","usr/libexec/veci-sms-drafts")],
 "sms_send_and_delete":[(SMS+"veci-sms-send-one","usr/libexec/veci-sms-send-one"),
                        (SMS+"veci-sms-delete-one","usr/libexec/veci-sms-delete-one")],
 "sms_multipart_pdu":[(UI+"veci2/sms-codec.js","www/veci2/sms-codec.js")],
 "sms_security_and_storage":[(UI+"veci2/sms-center.js","www/veci2/sms-center.js")],
 "system_services_startup":[(RTL+"veci2-services","usr/libexec/rpcd/veci.v2.services")],
 "system_cron_scheduler":[(RTL+"veci2-cron","usr/libexec/rpcd/veci.v2.cron")],
 "system_logs_diagnostics":[(RTL+"veci2-system-admin","usr/libexec/rpcd/veci.v2.system")],
 "system_time_ntp":[(RTL+"veci2-system-admin","usr/libexec/rpcd/veci.v2.system")],
 "system_leds_buttons":[(RTL+"veci2-system-admin","usr/libexec/rpcd/veci.v2.system")],
 "system_access_ssh_https":[(RTL+"veci2-access","usr/libexec/rpcd/veci.v2.access")],
 "system_backup_restore":[(RTL+"veci2-restore-check","usr/libexec/veci2-restore-check"),
                          (UI+"cgi-bin/veci2-restore","www/cgi-bin/veci2-restore"),
                          (UI+"cgi-bin/veci2-backup","www/cgi-bin/veci2-backup")],
 "system_manual_sysupgrade":[(RTL+"veci2-verify-image","usr/libexec/veci2-verify-image"),
                             (UI+"cgi-bin/veci2-verify","www/cgi-bin/veci2-verify")],
 "system_signed_github_ota":[(UI+"veci2/app.js","www/veci2/app.js"),
                              (RTL+"veci2-verify-image","usr/libexec/veci2-verify-image")],
 "system_update_policy":[(RTL+"veci2-update-policy","usr/libexec/rpcd/veci.v2.updatepolicy")],
 "addon_signed_package_manager":[(PKG+"veci2-apk","usr/libexec/rpcd/veci.v2.pkg")],
 "addon_enable_disable":[(RTL+"veci2-addon","usr/libexec/rpcd/veci.v2.addon"),
                         (RTL+"veci2-services","usr/libexec/rpcd/veci.v2.services")],
 "firmware_network_watchdog":[(WE+"usr/sbin/we5927-lte","usr/sbin/we5927-lte"),
                               (GUARD+"veci-wifi-guardian","usr/sbin/veci-wifi-guardian")],
 "firmware_gpio_hardware_watchdog":[(RTL+"veci2-gpio-watchdog","usr/libexec/veci2-gpio-watchdog"),
                                    (RTL+"veci2-watchdog-status","usr/libexec/rpcd/veci.v2.watchdog")],
 "firmware_24x7_observability":[(RTL+"veci2-observe","usr/libexec/veci2-observe"),
                                (RTL+"veci2-observe-rpc","usr/libexec/rpcd/veci.v2.observability"),
                                (RTL+"files/etc/init.d/veci2-observe","etc/init.d/veci2-observe")],
 "guest_wifi_isolation":[(RTL+"veci2-guest-check","usr/libexec/rpcd/veci.v2.guest")],
 "system_ipv6_off_by_default":[(IPV6+"etc/config/veci2_ipv6","etc/config/veci2_ipv6"),
                               (IPV6+"etc/init.d/veci2-ipv6","etc/init.d/veci2-ipv6")],
 "system_ipv6_guarded_settings_toggle":[(IPV6+"usr/libexec/rpcd/veci2-ipv6","usr/libexec/rpcd/veci.v2.ipv6")],
 "ui_four_group_navigation":[(UI+"veci2/index.html","www/veci2/index.html")]
}

def _squashfs_digest(path: Path) -> str:
    """Hash ROM bytes without changing the sensitive permissions in the image.

    unsquashfs must run with root privileges to reconstruct /dev/console. It
    also recreates owner-only (0600) configuration files, intentionally
    unreadable to the ordinary CI user. Prefer a normal read, and for those
    protected files only ask sudo to calculate their SHA-256 digest. Never
    execute checked-out Python code as root and never print config contents.
    """
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except PermissionError:
        try:
            result = subprocess.run(
                ["sudo", "-n", "sha256sum", "--", str(path)],
                capture_output=True,
                text=True,
                timeout=12,
                check=True,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError("PROTECTED_ROM_HASH_UNAVAILABLE") from exc
        digest = result.stdout.split(maxsplit=1)[0] if result.stdout else ""
        if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise RuntimeError("PROTECTED_ROM_HASH_INVALID")
        return digest


def check(rom:Path)->list[str]:
    errors=[]
    ids=[x["id"] for x in json.loads(CONTRACT.read_text())["required_core"]]
    if len(ids)!=39 or len(set(ids))!=39 or "lte_ussd" in ids or set(ids)!=set(FEATURES):
        return ["FEATURE_MAP_NOT_EXACTLY_39_ACTIVE"]
    if not rom.is_dir() or rom.is_symlink():
        return ["INVALID_IMAGE_ROOT"]
    checked=0
    for name in ids:
        entries=FEATURES.get(name,[])
        if not entries:
            errors.append("NO_ROM_EVIDENCE:"+name)
        for relative_source,relative_rom in entries:
            src=ROOT/relative_source
            dst=rom/relative_rom
            checked+=1
            if not src.is_file() or src.is_symlink():
                errors.append("MISSING_SOURCE:"+name+":"+relative_source)
                continue
            if not dst.is_file() or dst.is_symlink() or dst.stat().st_size!=src.stat().st_size:
                errors.append("ROM_MISSING_OR_WRONG_SIZE:"+name+":"+relative_rom)
                continue
            try:
                expected_digest = hashlib.sha256(src.read_bytes()).hexdigest()
                image_digest = _squashfs_digest(dst)
            except (OSError, RuntimeError) as exc:
                # A missing sudo privilege, malformed digest, or inaccessible
                # protected file is a HARD FAIL rather than a silent skip.
                errors.append("ROM_HASH_UNAVAILABLE:"+name+":"+relative_rom+":"+str(exc))
                continue
            if expected_digest != image_digest:
                errors.append("ROM_DIFFERENT_FROM_VERIFIED_SOURCE:"+name+":"+relative_rom)
    for forbidden in ("www/cgi-bin/luci","www/luci-static","usr/share/luci"):
        if (rom/forbidden).exists():
            errors.append("LUCI_PRESENT:"+forbidden)
    if not errors:
        print(f"EXACT_39_ACTIVE_CORE_ROM_PAYLOADS=PASS checked_files={checked}")
        print("NOT_A_HARDWARE_UAT_NOT_SIGNED_NOT_FLASH_APPROVED")
    return errors

if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("usage: check-all-core-rom.py <extracted-final-squashfs>")
    problems=check(Path(sys.argv[1]))
    if problems:
        print("\n".join(problems),file=sys.stderr)
        raise SystemExit(3)
