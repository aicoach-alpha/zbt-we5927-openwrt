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

def parsed_time(sample):
    """Reject timestamps that cannot locate a sample in an absolute UAT window."""
    value = sample.get("collected_at")
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None or dt.utcoffset() is None:
            return None
        return dt.timestamp()
    except (ValueError, OverflowError, TypeError):
        return None


def analyze(samples, interval=30, expected_hours=None):
    # Fixed UAT windows start at the FIRST recorded poll (successful or not).
    # Using the first successful SSH poll lets an initial multi-hour outage
    # disappear from the denominator, and late samples can fake 99% coverage.
    if interval < 1 or (expected_hours is not None and expected_hours <= 0):
        raise ValueError("invalid_window")
    dated = sorted(
        [(ts, sample) for sample in samples
         if (ts := parsed_time(sample)) is not None],
        key=lambda value: value[0])
    if not dated:
        return {"status": "insufficient_samples", "count": len(samples),
                "valid": 0, "coverage_percent": 0.0}
    start = dated[0][0]
    end = start + expected_hours * 3600 if expected_hours is not None else None
    in_window = [(ts, sample) for ts, sample in dated
                 if end is None or ts < end]
    # Do not count claimed "ok" records with missing/invalid decisive probes.
    # Missing usb0_carrier when usb0 is absent is still a valid outage sample.
    required = ("usb0_ipv4", "lte_default_route", "public_ping_ok")
    good = [(ts, sample) for ts, sample in in_window
            if sample.get("collection_status") == "ok"
            and all(type(sample.get(k)) is int and sample[k] in (0, 1)
                    for k in required)
            and (sample.get("usb0_carrier") in (0, 1)
                 or (sample.get("usb0_carrier") is None
                     and sample["usb0_ipv4"] == 0
                     and sample["lte_default_route"] == 0))]
    observed_span = max(0, good[-1][0] - good[0][0]) if good else 0
    expected = (max(1, ceil(expected_hours * 3600 / interval))
                if expected_hours is not None
                else max(1, int(round((dated[-1][0] - start) / interval)) + 1))
    if not good:
        return {"status": "insufficient_samples", "count": len(samples),
                "valid": 0, "expected": expected,
                "coverage_percent": 0.0,
                "out_of_window_samples": len(dated) - len(in_window)}
    events = []
    prev = None
    skipped_gaps = 0
    for t, s in good:
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
    # Only slots inside the requested window count; duplicate polls cannot
    # inflate coverage and observations after the deadline cannot repair gaps.
    unique_slots = {
        slot for t, _ in good
        if 0 <= (slot := int(round((t - start) / interval))) < expected
    }
    covered = min(len(unique_slots), expected)
    wifi = [x.get("external_ssid_visible") for _, x in in_window]
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
        "out_of_window_samples": len(dated) - len(in_window),
        "invalid_timestamp_samples": len(samples) - len(dated),
        "observed_span_seconds": round(observed_span, 1),
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
