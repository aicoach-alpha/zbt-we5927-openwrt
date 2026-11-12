#!/usr/bin/env python3
"""Read-only WE5927 hardware-UAT snapshot from a Windows Ethernet laptop.

This is not a burn-in test, firmware installer, or substitute for two-phone UAT.
Never changes router settings, Wi-Fi radio, modem, kernel, or Windows tasks.
Requires Python 3 and paramiko, an existing SSH RSA key and a pinned host key.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time


def parse_scan(output, expected):
    # Do not serialize SSID names, BSSIDs or other users' network names.
    entries = re.findall(r"(?mi)^\s*SSID\s+\d+\s*:\s*(.*?)\s*$", output)
    return {"visible": expected in entries, "networks_seen": len(entries),
            "scan_valid": len(entries) > 0}


def parse_reset(output):
    return {key.strip(): int(value) for key, value in re.findall(
        r"(?m)^([\w /-]+):\s*(\d+)\s*$", output)}


def read_remote(transport, command, seconds=9):
    ch = transport.open_session(timeout=5)
    ch.exec_command(command)
    result = bytearray()
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if ch.recv_ready():
            result.extend(ch.recv(8192))
            if len(result) > 32768:
                ch.close()
                raise RuntimeError("router response too large")
        if ch.exit_status_ready():
            while ch.recv_ready():
                result.extend(ch.recv(8192))
            rc = ch.recv_exit_status()
            ch.close()
            return rc, result.decode(errors="replace")
        time.sleep(0.07)
    ch.close()
    raise TimeoutError("router read-only query exceeded deadline")


def snapshot(host, key_file, pin):
    import paramiko
    t = paramiko.Transport((host, 22))
    try:
        t.start_client(timeout=10)
        fingerprint = base64.b64encode(hashlib.sha256(
            t.get_remote_server_key().asbytes()).digest()).decode().rstrip("=")
        if fingerprint != pin.removeprefix("SHA256:"):
            raise RuntimeError("SSH host key mismatch")
        key = paramiko.RSAKey.from_private_key_file(str(key_file))
        t.auth_publickey("root", key)
        if not t.is_authenticated():
            raise RuntimeError("SSH authentication failed")

        # Commands listed here are READ ONLY. Never add wifi reload, ifdown,
        # sysupgrade, service restart, AT modem state-changing commands, etc.
        probes = {
            "kernel": "uname -r",
            "radio": "ubus -S -t 3 call network.wireless status '{}'",
            "hostapd": "ubus -S -t 3 call hostapd.phy0-ap0 get_status '{}'",
            "driver": "cat /sys/kernel/debug/ieee80211/phy0/mt76/reset",
            "guardian": "cat /tmp/veci-wifi-performance.state",
            "lte": "ubus -S -t 3 call network.interface.lte status '{}'",
            "gateway": "ping -I usb0 -c 1 -W 2 192.168.7.1 >/dev/null 2>&1",
            "public_ip": "ping -I usb0 -c 1 -W 2 1.1.1.1 >/dev/null 2>&1",
            "route": "ip -4 route show default dev usb0",
            "rpcd": "ps | grep '[r]pcd -s'",
            "guest": "uci -q get wireless.veci_guest.disabled; uci -q get uhttpd.veci_guest.enabled",
        }
        values = {}
        for name, command in probes.items():
            try:
                values[name] = read_remote(t, command)
            except (TimeoutError, OSError, RuntimeError):
                values[name] = (124, "")
        def decoded(name):
            rc, raw = values[name]
            if rc != 0:
                return {}
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {}
        radio = decoded("radio").get("radio0", {})
        hostapd = decoded("hostapd")
        lte = decoded("lte")
        kernel = values["kernel"][1].strip() if values["kernel"][0] == 0 else ""
        return {
            "kernel_version": kernel,
            "radio_up": radio.get("up") is True,
            "hostapd_enabled": hostapd.get("status") == "ENABLED",
            "channel": hostapd.get("channel"),
            "driver_reset_counters": parse_reset(values["driver"][1]),
            "guardian_safe": "auto_recover=0" in values["guardian"][1],
            "beacon_external_verification_not_inferred": "beacon_verified=0" in values["guardian"][1],
            "lte_up": lte.get("up") is True,
            "lte_device_usb0": lte.get("l3_device") == "usb0",
            "gateway_ping": values["gateway"][0] == 0,
            "public_ip_ping": values["public_ip"][0] == 0,
            "lte_default_route": "default via" in values["route"][1] and "dev usb0" in values["route"][1],
            "rpcd_running": values["rpcd"][0] == 0 and "rpcd -s" in values["rpcd"][1],
            "guest_off": values["guest"][1].splitlines() == ["1", "0"],
            "remote_query_errors": [n for n, (rc, _) in values.items() if rc != 0],
        }
    finally:
        t.close()


def run(args):
    if not sys.platform.startswith("win"):
        raise RuntimeError("independent SSID scanner requires Windows netsh")
    report = {"utc": datetime.now(timezone.utc).isoformat(), "mode": "READ_ONLY_SNAPSHOT",
              "no_firmware_changes": True, "no_radio_reloads": True}
    scans = []
    for i in range(args.samples):
        scan = subprocess.run(["netsh.exe", "wlan", "show", "networks", "mode=bssid"],
                              capture_output=True, text=True, errors="replace", timeout=12)
        item = parse_scan(scan.stdout, args.ssid)
        item["scan_valid"] = item["scan_valid"] and scan.returncode == 0
        scans.append(item)
        print(f"Scan {i + 1}/{args.samples}: visible={item['visible']}, other networks seen={item['networks_seen']}", flush=True)
        if i + 1 < args.samples:
            time.sleep(args.interval)
    report["external_scans"] = scans
    report["router"] = snapshot(args.host, args.key, args.host_key_pin)
    h = report["router"]
    checks = {
        "all_external_scans_detect_ssid": all(x["visible"] and x["scan_valid"] for x in scans),
        "radio_control_plane": h["radio_up"] and h["hostapd_enabled"],
        "rpcd": h["rpcd_running"],
        "local_lte_gateway": h["lte_up"] and h["lte_default_route"] and h["gateway_ping"],
        "guest_disabled": h["guest_off"],
    }
    if args.expected_kernel:
        checks["kernel_version"] = h["kernel_version"] == args.expected_kernel
    report["checks"] = checks
    report["snapshot_pass"] = all(checks.values())
    report["72_hour_uat_complete"] = False
    args.output.parent.mkdir(exist_ok=True, parents=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"SNAPSHOT_PASS={report['snapshot_pass']}")
    print(f"LOCAL_REPORT={args.output}")
    print("ROUTER_CHANGES=NONE")
    return 0 if report["snapshot_pass"] else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", required=True)
    ap.add_argument("--ssid", required=True)
    ap.add_argument("--host-key-pin", required=True)
    ap.add_argument("--key", required=True, type=Path)
    ap.add_argument("--expected-kernel", default="")
    ap.add_argument("--samples", type=int, default=3)
    ap.add_argument("--interval", type=float, default=2)
    ap.add_argument("--output", required=True, type=Path)
    a = ap.parse_args()
    if not 1 <= a.samples <= 15 or not 0 <= a.interval <= 30 or not a.key.is_file():
        ap.error("invalid samples, interval, or SSH key path")
    return run(a)


if __name__ == "__main__":
    sys.exit(main())
