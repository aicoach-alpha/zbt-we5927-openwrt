#!/usr/bin/env python3
"""Collect read-only VeCI router counters on a WIRED management laptop.

No router files, services, settings or credentials are read or written.
Logs are sanitized locally, omit IPs, SSIDs, modem IDs and SMS contents.
"""
import argparse
from datetime import datetime, timezone
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import sys
import time

KEYS = {
    "epoch_s", "uptime_s", "usb0_carrier", "usb0_operstate",
    "usb0_ipv4", "lte_default_route", "gateway_ping_ok",
    "public_ping_ok", "usb0_rx_errors", "usb0_tx_errors",
    "usb0_rx_dropped", "usb0_tx_dropped", "ubus_responsive",
    "mt76_mcu_timeout_log_count", "dhcp_release_log_count",
    "dhcp_renew_log_count", "usb_disconnect_log_count",
    "wifi_kernel_stall_log_count", "mem_available_kib",
}
INTEGER = KEYS - {"usb0_operstate"}
INTPAT = re.compile(r"\d+\Z")
# A successful SSH exit is not evidence that the core telemetry parsed.
# A physically missing USB interface reports unknown carrier/operstate,
# but its absence is itself important outage evidence, not a failed poll.
BINARY_REQUIRED = ("usb0_ipv4", "lte_default_route", "public_ping_ok")


def snapshot_valid(record):
    return (len(record) >= 12
            and type(record.get("epoch_s")) is int and record["epoch_s"] > 0
            and type(record.get("uptime_s")) is int and record["uptime_s"] >= 0
            and all(type(record.get(k)) is int and record[k] in (0, 1)
                    for k in BINARY_REQUIRED)
            and (record.get("usb0_carrier") in (0, 1)
                 or (record.get("usb0_carrier") is None
                     and record["usb0_ipv4"] == 0
                     and record["lte_default_route"] == 0)))


SSIDPAT = re.compile(r"^\s*SSID\s+\d+\s*:\s*(.*?)\s*$", re.MULTILINE)


def parse_snapshot(stdout):
    result = {}
    for line in stdout.splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k not in KEYS:
            continue
        if k == "usb0_operstate":
            result[k] = v if v in {"up", "down", "dormant", "unknown", "?"} else "?"
        else:
            result[k] = int(v) if INTPAT.fullmatch(v) else None
    return result


def scan_ssid(ssid):
    if not ssid:
        return None
    if sys.platform != "win32":
        return None
    try:
        cp = subprocess.run(
            ["netsh", "wlan", "show", "networks", "mode=bssid"],
            capture_output=True, text=True, errors="replace", timeout=8,
            check=False,
        )
        if cp.returncode:
            return None
        return any(s == ssid for s in SSIDPAT.findall(cp.stdout))
    except (OSError, subprocess.TimeoutExpired):
        return None


def sample(host, key, known_hosts, source, ssid):
    cmd = [
        "ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
        "-o", "ConnectionAttempts=1", "-o", "StrictHostKeyChecking=yes",
        "-o", f"UserKnownHostsFile={known_hosts}", "-o", "LogLevel=ERROR",
        "-i", str(key), f"root@{host}", "sh", "-s",
    ]
    try:
        cp = subprocess.run(cmd, input=source, capture_output=True, text=True,
                            timeout=16, check=False)
        # Do not save stdout or stderr, even on error.
        record = parse_snapshot(cp.stdout) if cp.returncode == 0 else {}
        status = "ok" if cp.returncode == 0 and snapshot_valid(record) else "unavailable"
    except (OSError, subprocess.TimeoutExpired):
        record, status = {}, "unavailable"
    record.update({"collected_at": datetime.now(timezone.utc).isoformat(),
                   "collection_status": status, "external_ssid_visible": scan_ssid(ssid)})
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", required=True, help="exact IPv4 of router on wired LAN")
    p.add_argument("--key", required=True, type=Path, help="existing private SSH key")
    p.add_argument("--known-hosts", required=True, type=Path,
                   help="pre-verified pinned SSH host key file")
    p.add_argument("--out", required=True, type=Path, help="local JSONL file")
    p.add_argument("--ssid", default=None, help="compare locally; never saved in output")
    p.add_argument("--hours", type=float, default=72.0)
    p.add_argument("--interval", type=int, default=30)
    args = p.parse_args()
    try:
        ipaddress.IPv4Address(args.host)
    except ipaddress.AddressValueError:
        p.error("--host must be an IPv4 address")
    if not args.key.is_file() or not args.known_hosts.is_file():
        p.error("existing SSH key and pinned known_hosts are required")
    if not 0 < args.hours <= 168 or not 10 <= args.interval <= 300:
        p.error("invalid --hours or --interval")
    if not Path(__file__).with_name("veci-link-readonly-snapshot.sh").is_file():
        p.error("read-only snapshot source missing")
    source = Path(__file__).with_name("veci-link-readonly-snapshot.sh").read_text()
    if args.out.exists():
        p.error("refusing to overwrite an existing monitoring log")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    end = time.monotonic() + args.hours * 3600
    with args.out.open("x", encoding="utf-8") as f:
        while time.monotonic() < end:
            start = time.monotonic()
            record = sample(args.host, args.key, args.known_hosts, source, args.ssid)
            f.write(json.dumps(record, separators=(",", ":")) + "\n")
            f.flush()
            time.sleep(max(0, args.interval - (time.monotonic() - start)))


if __name__ == "__main__":
    main()
