"""Offline contract tests for read-only wired MT7603 UAT scanner."""
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "uat/mt7603_wired_snapshot.py"
spec = importlib.util.spec_from_file_location("mt7603_wired_snapshot", SOURCE)
sut = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sut)


class UatSafety(unittest.TestCase):
    def test_scan_detects_only_exact_ssid(self):
        data = """Interface name : Wi-Fi
There are 2 networks currently visible.
SSID 1 : Example-Office
    Network type : Infrastructure
SSID 2 : Example-Guest
    Network type : Infrastructure
"""
        self.assertTrue(sut.parse_scan(data, "Example-Office")["visible"])
        self.assertFalse(sut.parse_scan(data, "Example")["visible"])
        self.assertFalse(sut.parse_scan(data, "Example-Office2")["visible"])
        self.assertEqual(sut.parse_scan(data, "Example-Office")["networks_seen"], 2)

    def test_empty_scan_is_invalid_not_success(self):
        self.assertFalse(sut.parse_scan("No networks found.", "Example-Office")["scan_valid"])

    def test_driver_reset_counters(self):
        data = "TX hang: 0\nRX PSE busy stuck: 1\nBeacon stuck: 0\nMCU hang: 0\n"
        parsed = sut.parse_reset(data)
        self.assertEqual(parsed["RX PSE busy stuck"], 1)
        self.assertEqual(parsed["Beacon stuck"], 0)

    def test_no_mutating_router_operations(self):
        src = SOURCE.read_text()
        query_block = src.split("probes = {", 1)[1].split("\n        }", 1)[0]
        for forbidden in ["wifi reload", "wifi up", "wifi down", "ifdown",
                          "ifup", "reboot", "sysupgrade", "uci commit", "uci set",
                          "power-cycle", "service restart"]:
            self.assertNotIn(forbidden, query_block)
        self.assertIn("ubus -S -t 3", query_block)

    def test_does_not_expose_ssid_or_private_key_in_report(self):
        src = SOURCE.read_text()
        self.assertNotIn('"ssid": args.ssid', src)
        self.assertNotIn('"private_key":', src)
        self.assertIn('report["72_hour_uat_complete"] = False', src)
        self.assertIn('"no_firmware_changes": True', src)


if __name__ == "__main__":
    unittest.main()
