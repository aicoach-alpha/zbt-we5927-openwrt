"""Ensure Windows physical UAT cannot recreate accidental second netifd."""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"scripts/uat/veci-office-readonly.ps1"
SOURCE=SCRIPT.read_text(encoding="utf-8")

class OfficeUatContract(unittest.TestCase):
    def test_remote_commands_are_literal_read_only_invocations(self):
        # Ban pipes, chaining and metacharacters at the exact remote callsite.
        remote_lines=[line.strip() for line in SOURCE.splitlines()
                      if re.search(r"\bRead-Router(?:Json)?\s+['\"]",line)]
        self.assertGreaterEqual(len(remote_lines), 10)
        for line in remote_lines:
            with self.subTest(cmd=line):
                self.assertNotIn("|",line)
                self.assertNotIn(";",line)
                self.assertNotIn("&&",line)
                self.assertNotIn(chr(96),line)
                self.assertNotRegex(line,r"(?i)\b(ifdown|ifup|kill|reboot|sysupgrade|uci\s+(commit|set)|wifi\s+(reload|up|down)|netifd\s*&)\b")
        self.assertIn("Read-Router 'pidof netifd'",SOURCE)
        self.assertNotIn("Read-Router 'netifd'",SOURCE)
        self.assertIn("StrictHostKeyChecking=yes",SOURCE)
        self.assertIn("BatchMode=yes",SOURCE)

    def test_no_modem_radio_or_ethernet_restarts(self):
        for snippet in ("'/etc/init.d/network restart'", "'/etc/init.d/we5927-lte restart'",
                        "'/usr/sbin/we5927-lte usb-repair'", "'wifi reload'",
                        "'ifdown wan'", "'ifup lte'"):
            self.assertNotIn(snippet,SOURCE)
        self.assertIn("router_configuration_modified = $false",SOURCE)
        self.assertIn("firmware_flash_authorized = $false",SOURCE)
        self.assertIn("all_lan_ports_physical_tested = $false",SOURCE)
        self.assertIn("wired_client_internet_verified = $null",SOURCE)
        self.assertIn("wifi_client_internet_verified = $null",SOURCE)
        self.assertIn("Router-LTE-uplink=",SOURCE)

    def test_never_claims_wifi_beacon_from_router_control_plane(self):
        self.assertIn("external_verified_bssid_visible",SOURCE)
        self.assertIn("ExpectedSSID",SOURCE)
        self.assertIn("ExpectedBSSID",SOURCE)
        self.assertIn("all_samples_wifi_beacon_pass",SOURCE)
        self.assertIn("if (-not $ExpectedBSSID) { $null }",SOURCE)
        self.assertIn("all_lan_ports_physical_tested = $false",SOURCE)
        self.assertIn("wired_client_internet_verified = $null",SOURCE)
        self.assertIn("wifi_client_internet_verified = $null",SOURCE)
        self.assertIn("Router-LTE-uplink=",SOURCE)
        self.assertNotIn("wifi_beacon_pass = $apState",SOURCE)

    def test_ap_service_diagnostics_cannot_confuse_radio_up_with_beacon(self):
        self.assertIn("Read-Router 'ubus -S -t 3 list hostapd.phy0-ap0'", SOURCE)
        self.assertIn("Read-Router '/etc/init.d/wpad status'", SOURCE)
        self.assertIn("hostapd_ubus_registered =", SOURCE)
        self.assertIn("wpad_service_running =", SOURCE)
        self.assertIn("radio_and_ap_status_conflict =", SOURCE)
        self.assertIn("wifi_beacon_pass = $externalSeen", SOURCE)

    def test_report_excludes_secret_telemetry(self):
        # Only safe summaries/port flags are output: avoid raw passwords, SSID,
        # host fingerprint, IMEI or carrier APN in persisted observations.
        section=SOURCE.split("return [pscustomobject]@{",1)[1].split("\n    }",1)[0]
        for secret in ("imei","imsi","iccid","apn","macaddr","password",
                       "ssid =","bssid =","ip_address","raw_"):
            self.assertNotIn(secret,section.lower())

if __name__=="__main__":
    unittest.main()
