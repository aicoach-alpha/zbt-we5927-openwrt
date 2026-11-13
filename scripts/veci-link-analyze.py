#!/usr/bin/env python3
"""Analyze sanitized wired-monitor JSONL; never claim root cause from ICMP alone."""
import argparse
from datetime import datetime
from math import ceil
import json
from pathlib import Path
from statistics import median

def asnum(row, key):
    value = row.get(key)
    return value if type(value) in (int, float) else None

def analyze(samples, interval=30, expected_hours=None):
    # Use the requested monitoring duration for release qualification. Computing
    # expected only from first/last successful SSH polls hides entire outages.
    if interval < 1 or (expected_hours is not None and expected_hours <= 0):
        raise ValueError("invalid_window")
    # Do not count a claimed "ok" JSONL line if decisive link/probe
    # telemetry is absent, malformed, or a JSON boolean.
    required = ("usb0_ipv4", "lte_default_route", "public_ping_ok")
    good = [s for s in samples
            if s.get("collection_status") == "ok"
            and all(type(s.get(k)) is int and s[k] in (0, 1)
                    for k in required)]
    if not good:
        return {"status": "insufficient_samples", "count": len(samples)}
    events = []
    prev = None
    skipped_gaps = 0
    for s in good:
        t = datetime.fromisoformat(s["collected_at"]).timestamp()
        contiguous = prev is not None and 0 < t - prev[0] <= max(interval * 2.5, 20)
        if prev is not None and not contiguous:
            skipped_gaps += 1
        if contiguous and asnum(prev[1], "public_ping_ok") == 1 and asnum(s, "public_ping_ok") == 0:
            p = prev[1]
            dhcp = all(asnum(x, "dhcp_release_log_count") is not None for x in (p, s)) and (
                s["dhcp_release_log_count"] > p["dhcp_release_log_count"])
            usb = all(asnum(x, "usb_disconnect_log_count") is not None for x in (p, s)) and (
                s["usb_disconnect_log_count"] > p["usb_disconnect_log_count"])
            local = s.get("usb0_carrier") == 1 and s.get("usb0_ipv4") == 1 and (
                s.get("lte_default_route") == 1)
            events.append({
                "at": s["collected_at"],
                "lte_local_link_present": local,
                "gateway_ping_ok": s.get("gateway_ping_ok"),
                "lease_release_log_increment": dhcp,
                "usb_disconnect_log_increment": usb,
                "classification": (
                    "usb_disconnect_suspected" if usb else
                    "dhcp_release_suspected" if dhcp else
                    "upstream_or_probe_degraded" if local else "lte_local_path_degraded"
                )
            })
        prev = (t, s)
    times = [datetime.fromisoformat(x["at"]).timestamp() for x in events]
    gaps = [(b - a) / 60 for a, b in zip(times, times[1:])]
    periodic = len(gaps) >= 2 and all(115 <= d <= 130 for d in gaps)
    observed_span = max(0, (datetime.fromisoformat(good[-1]["collected_at"]) -
                            datetime.fromisoformat(good[0]["collected_at"])).total_seconds())
    expected = (max(1, ceil(expected_hours * 3600 / interval)) if expected_hours is not None
                else max(1, int(round(observed_span / interval)) + 1))
    # Duplicate or sub-interval samples do not increase monitoring coverage.
    timestamps = sorted({int(datetime.fromisoformat(x["collected_at"]).timestamp())
                         for x in good})
    unique_slots = set()
    if timestamps:
        first = timestamps[0]
        for t in timestamps:
            slot = int(round((t - first) / interval))
            if slot >= 0:
                unique_slots.add(slot)
    covered = min(len(unique_slots), expected)
    wifi = [x.get("external_ssid_visible") for x in samples]
    ssid_miss = sum(v is False for v in wifi)
    wifi_observed = sum(v is not None for v in wifi)
    return {
        "status": "observation_only",
        "collected": len(samples),
        "valid": len(good),
        "unique_valid_slots": len(unique_slots),
        "expected": expected,
        "expected_hours": expected_hours,
        "coverage_percent": round(100 * covered / expected, 2),
        "disconnected_sample_gaps": skipped_gaps,
        "outage_edges": events,
        "minutes_between_edges": [round(x, 1) for x in gaps],
        "median_minutes_between_edges": round(median(gaps), 1) if gaps else None,
        "122_minute_pattern_consistent": periodic,
        "external_ssid_scans": wifi_observed,
        "external_ssid_missing_scans": ssid_miss,
        "interpretation": (
            "Pattern is temporal only; examine actual DHCP lease and operator/modem timestamps. "
            "ICMP may be filtered. Log-ring counts can wrap; use multiple signals. "
            "A functioning gateway + RNDIS does not justify modem reset."
        )
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("jsonl", type=Path)
    p.add_argument("--interval", type=int, default=30)
    p.add_argument("--expected-hours", type=float, default=None,
                   help="requested UAT duration, e.g. 72; mandatory for acceptance")
    args = p.parse_args()
    if not 10 <= args.interval <= 300:
        p.error("invalid sample interval")
    if args.expected_hours is not None and not 0 < args.expected_hours <= 168:
        p.error("invalid expected hours")
    samples = []
    with args.jsonl.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    print(json.dumps(analyze(samples, args.interval, args.expected_hours), indent=2))

if __name__ == "__main__":
    main()
