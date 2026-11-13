"""Offline contract tests for read-only wired MT7603 UAT scanner."""
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "uat/mt7603_wired_snapshot.py"
spec = importlib.util.spec_from_file_location("mt7603_wired_snapshot", SOURCE)
sut = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sut)


class UatSafety(unittest.TestCase):
    def test_scan_detects_only_matching_ssid_and_bssid(self):
        data = """Interface name : Wi-Fi
There are 3 networks currently visible.
SSID 1 : Example-Office
    Network type : Infrastructure
    BSSID 1 : aa:bb:cc:dd:ee:11
SSID 2 : Example-Office
    Network type : Infrastructure
    BSSID 1 : aa:bb:cc:dd:ee:22
SSID 3 : Example-Guest
    Network type : Infrastructure
    BSSID 1 : aa:bb:cc:dd:ee:33
"""
        expected = sut.parse_scan(data, "Example-Office", "AA:BB:CC:DD:EE:22")
        self.assertTrue(expected["visible"])
        self.assertTrue(expected["identity_pinned"])
        self.assertEqual(expected["networks_seen"], 3)
        self.assertFalse(sut.parse_scan(data, "Example-Office",
                                        "AA:BB:CC:DD:EE:FF")["visible"])
        self.assertFalse(sut.parse_scan(data, "Example-Office2",
                                        "AA:BB:CC:DD:EE:22")["visible"])
        self.assertFalse(sut.parse_scan(data, "Example-Guest",
                                        "AA:BB:CC:DD:EE:22")["visible"])
        self.assertIsNone(sut.parse_scan(data, "Example-Office")["visible"])
        self.assertNotIn("aa:bb:cc:dd:ee", str(expected).lower())
        self.assertNotIn("Example-Office", str(expected))

    def test_empty_scan_is_invalid_not_success(self):
        self.assertFalse(sut.parse_scan("No networks found.", "Example-Office", "aa:bb:cc:dd:ee:ff")["scan_valid"])

    def test_bssid_parser_rejects_invalid_identity(self):
        with self.assertRaises(ValueError):
            sut.parse_scan("SSID 1 : Example-Office", "Example-Office", "AA:BB:CC:11")
        with self.assertRaises(ValueError):
            sut.parse_scan("SSID 1 : Example-Office", "Example-Office", "AA:BB-CC:DD:EE:FF")

    def test_ssid_without_bssid_is_not_ap_visibility_evidence(self):
        text = "SSID 1 : Example-Office\n    BSSID 1 : aa:bb:cc:dd:ee:11\n"
        report = sut.parse_scan(text, "Example-Office")
        self.assertTrue(report["scan_valid"])
        self.assertIsNone(report["visible"])
        self.assertFalse(report["identity_pinned"])

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
        self.assertIn('ap.add_argument("--bssid", required=True', src)


if __name__ == "__main__":
    unittest.main()
