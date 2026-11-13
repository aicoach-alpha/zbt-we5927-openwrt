#!/usr/bin/env python3
"""Parse Windows netsh Wi-Fi scans for one explicitly pinned AP identity.

Never return or serialize scanned SSIDs/BSSIDs. A matching SSID from a
different AP is NOT evidence that the WE5927 radio is beaconing.
This is RF observation, not cryptographic AP authentication.
"""
import re

SSID_LINE = re.compile(r"^\s*SSID\s+\d+\s*:\s*(.*?)\s*$", re.I)
BSSID_LINE = re.compile(r"^\s*BSSID\s+\d+\s*:\s*([0-9a-fA-F:-]+)\s*$", re.I)
MAC = re.compile(r"^[0-9a-fA-F]{2}([:-])[0-9a-fA-F]{2}(?:[:-][0-9a-fA-F]{2}){4}$")


def normalize_bssid(value):
    if not isinstance(value, str) or not MAC.fullmatch(value):
        raise ValueError("expected --bssid as six hexadecimal octets")
    separators = {c for c in value if c in ":-"}
    if len(separators) != 1:
        raise ValueError("inconsistent BSSID separators")
    return value.replace(":", "").replace("-", "").lower()


def parse_scan(output, expected_ssid, expected_bssid):
    """Return only scalar observations; never disclose network identifiers."""
    pin = normalize_bssid(expected_bssid) if expected_bssid else None
    current_ssid = None
    networks_seen = 0
    target_visible = False
    for line in output.splitlines():
        found_ssid = SSID_LINE.fullmatch(line)
        if found_ssid:
            networks_seen += 1
            current_ssid = found_ssid.group(1)
            continue
        found_bssid = BSSID_LINE.fullmatch(line)
        if found_bssid and current_ssid == expected_ssid and pin:
            try:
                target_visible |= normalize_bssid(found_bssid.group(1)) == pin
            except ValueError:
                # Malformed AP advertising must not count as physical evidence.
                pass
    return {
        "visible": target_visible if pin and expected_ssid else None,
        "scan_valid": networks_seen > 0,
        "networks_seen": networks_seen,
        "identity_pinned": bool(pin and expected_ssid),
    }
