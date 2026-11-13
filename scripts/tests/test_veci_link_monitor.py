import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest

ROOT=Path(__file__).resolve().parents[1]
def load(name, path):
    s=importlib.util.spec_from_file_location(name, str(path))
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
monitor=load("veci_monitor", ROOT/"veci-link-wired-monitor.py")
analyzer=load("veci_analyze", ROOT/"veci-link-analyze.py")

def row(minute, up, **kw):
    return {
        "collected_at": (datetime(2026,11,12,tzinfo=timezone.utc) +
                         timedelta(minutes=minute)).isoformat(),
        "collection_status": "ok", "public_ping_ok": up,
        "usb0_carrier":1, "usb0_ipv4":1, "lte_default_route":1,
        "gateway_ping_ok":1, "dhcp_release_log_count":0,
        "usb_disconnect_log_count":0, "external_ssid_visible":True,
        **kw,
    }

class Tests(unittest.TestCase):
    def test_snapshot_filters_private_fields(self):
        out=monitor.parse_snapshot("epoch_s=42\nusb0_carrier=1\nssid=PRIVATE\nimei=SECRET\n"
                                   "usb0_operstate=up\n")
        self.assertEqual(out,{"epoch_s":42,"usb0_carrier":1,"usb0_operstate":"up"})
    def test_successful_ssh_with_unparsed_metrics_is_not_valid_telemetry(self):
        malformed="\n".join(f"{k}=?" for k in monitor.KEYS) + "\n"
        with patch.object(monitor.subprocess, "run",
                          return_value=SimpleNamespace(returncode=0, stdout=malformed)):
            with patch.object(monitor, "scan_ssid", return_value=None):
                result=monitor.sample("192.168.1.1", Path("unused"),
                                      Path("unused"), "echo ignored", None)
        self.assertEqual(result["collection_status"], "unavailable")
        self.assertIsNone(result["public_ping_ok"])

    def test_missing_usb_interface_is_a_valid_observation_not_missing_data(self):
        data = {k: 0 for k in monitor.KEYS if k != "usb0_operstate"}
        data.update(epoch_s=1794500000, uptime_s=1200,
                    usb0_carrier=None, usb0_ipv4=0, lte_default_route=0,
                    public_ping_ok=0, usb0_operstate="?")
        self.assertTrue(monitor.snapshot_valid(data))
        samples = [row(0, 1), row(0.5, 0, usb0_carrier=None,
                 usb0_ipv4=0, lte_default_route=0)]
        result = analyzer.analyze(samples, interval=30)
        self.assertEqual(result["valid"], 2)
        self.assertEqual(len(result["outage_edges"]), 1)
        self.assertEqual(result["outage_edges"][0]["classification"],
                         "lte_local_path_degraded")

    def test_bad_telemetry_cannot_inflate_72h_coverage(self):
        valid=row(0,1)
        broken=[row(i*0.5,1,public_ping_ok=None) for i in range(1,120)]
        result=analyzer.analyze([valid]+broken, interval=30, expected_hours=1)
        self.assertEqual(result["valid"], 1)
        self.assertEqual(result["unique_valid_slots"], 1)
        self.assertLess(result["coverage_percent"], 2)

    def test_period_requires_multiple_cycles(self):
        s=[row(0,1),row(2,0),row(4,1),row(124,0),row(125,1),row(246,0)]
        self.assertTrue(analyzer.analyze(s,interval=3600)["122_minute_pattern_consistent"])
        self.assertEqual(len(analyzer.analyze(s,interval=3600)["outage_edges"]),3)
    def test_single_gap_not_evidence(self):
        s=[row(0,1),row(10,0),row(15,1),row(132,0)]
        self.assertFalse(analyzer.analyze(s)["122_minute_pattern_consistent"])
    def test_dhcp_release_is_suspected_only(self):
        a=row(0,1); b=row(1,0)
        b["dhcp_release_log_count"]=1
        result=analyzer.analyze([a,b])
        self.assertEqual(result["outage_edges"][0]["classification"], "dhcp_release_suspected")
    def test_wifi_visibility_must_be_observed_externally(self):
        a=row(0,1); a["external_ssid_visible"]=None
        b=row(1,1); b["external_ssid_visible"]=False
        res=analyzer.analyze([a,b])
        self.assertEqual(res["external_ssid_scans"],1)
        self.assertEqual(res["external_ssid_missing_scans"],1)
    def test_no_false_root_cause_from_ping(self):
        res=analyzer.analyze([row(0,1),row(1,0)])
        self.assertEqual(res["outage_edges"][0]["classification"],"upstream_or_probe_degraded")
        self.assertEqual(res["status"],"observation_only")

    def test_uat_coverage_uses_full_requested_72h_not_only_success_span(self):
        result=analyzer.analyze([row(0,1),row(0.5,0)],interval=30,expected_hours=72)
        self.assertEqual(result["expected"],8640)
        self.assertLess(result["coverage_percent"],1)
        self.assertEqual(result["unique_valid_slots"],2)

    def test_disconnected_monitor_gap_is_not_a_proven_wan_down_edge(self):
        result=analyzer.analyze([row(0,1),row(120,0)],interval=30,expected_hours=72)
        self.assertEqual(result["outage_edges"],[])
        self.assertEqual(result["disconnected_sample_gaps"],1)
        self.assertFalse(result["122_minute_pattern_consistent"])

    def test_duplicates_cannot_fake_99_percent_coverage(self):
        repeated=[row(0,1)]*200
        result=analyzer.analyze(repeated,interval=30,expected_hours=1)
        self.assertEqual(result["unique_valid_slots"],1)
        self.assertLess(result["coverage_percent"],2)

    def test_outside_requested_window_cannot_repair_missing_coverage(self):
        samples = [row(0, 1)] + [row(120 + i * 0.5, 1) for i in range(120)]
        result = analyzer.analyze(samples, interval=30, expected_hours=1)
        self.assertEqual(result["expected"], 120)
        self.assertEqual(result["valid"], 1)
        self.assertEqual(result["unique_valid_slots"], 1)
        self.assertEqual(result["out_of_window_samples"], 120)
        self.assertEqual(result["external_ssid_scans"], 1)
        self.assertLess(result["coverage_percent"], 1)

    def test_first_failed_poll_anchors_window_even_if_ssh_recovers_late(self):
        first = row(0, 1, public_ping_ok=None)
        later = [row(65 + i * 0.5, 1) for i in range(120)]
        result = analyzer.analyze([first] + later, interval=30, expected_hours=1)
        self.assertEqual(result["status"], "insufficient_samples")
        self.assertEqual(result["coverage_percent"], 0)
        self.assertEqual(result["out_of_window_samples"], 120)

    def test_unordered_logs_are_sorted_before_outage_classification(self):
        samples = [row(1, 1), row(0.5, 0), row(0, 1)]
        result = analyzer.analyze(samples, interval=30, expected_hours=1)
        self.assertEqual(result["valid"], 3)
        self.assertEqual(len(result["outage_edges"]), 1)
        self.assertEqual(result["disconnected_sample_gaps"], 0)

    def test_bad_timestamp_does_not_crash_or_expand_coverage(self):
        bad = row(0.5, 1)
        bad["collected_at"] = "not-an-absolute-time"
        result = analyzer.analyze([row(0, 1), bad], interval=30,
                                  expected_hours=1)
        self.assertEqual(result["valid"], 1)
        self.assertEqual(result["invalid_timestamp_samples"], 1)
        self.assertEqual(result["unique_valid_slots"], 1)

    def test_gap_recovery_must_not_invent_outage_edge(self):
        a=row(0,1); b=row(122,0); c=row(122.5,1)
        d=row(244.5,0)
        result=analyzer.analyze([a,b,c,d],interval=30)
        self.assertFalse(result["122_minute_pattern_consistent"])
        self.assertEqual(len(result["outage_edges"]),0)

if __name__=="__main__":
    unittest.main()
