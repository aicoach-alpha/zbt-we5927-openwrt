import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
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

if __name__=="__main__":
    unittest.main()
