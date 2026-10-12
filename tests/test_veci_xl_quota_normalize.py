import importlib.util
import sys
import unittest
from pathlib import Path
p=Path(__file__).resolve().parents[1]/"scripts/veci_xl_quota_normalize.py"
spec=importlib.util.spec_from_file_location("xlquota",p)
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m;spec.loader.exec_module(m)
class NormalizeTests(unittest.TestCase):
    def sample(self):
        return {"ok":True,"phone":"REDACT_NOT_EMITTED","quota":{"data":{"quotas":[
            {"end_date":1893456000,"benefits":[
                {"data_type":"DATA","total":10737418240,"remaining":5368709120},
                {"data_type":"VOICE","total":100,"remaining":30}
            ]}
        ]}}}
    def test_quota_and_privacy(self):
        r=m.normalize(self.sample())
        self.assertEqual(r["operator"],"xl")
        self.assertEqual(r["total_bytes"],10737418240)
        self.assertEqual(r["remaining_bytes"],5368709120)
        self.assertNotIn("phone",r)
        self.assertNotIn("token",r)
    def test_reject_greater_remaining(self):
        s=self.sample();s["quota"]["data"]["quotas"][0]["benefits"][0]["remaining"]=20000000000
        with self.assertRaises(ValueError):m.normalize(s)
    def test_reject_unauthorized(self):
        with self.assertRaises(ValueError):m.normalize({"ok":False,"message":"auth"})
    def test_missing_expiry_fails(self):
        s=self.sample();s["quota"]["data"]["quotas"][0].pop("end_date")
        with self.assertRaises(ValueError):m.normalize(s)
    def test_voice_only_fails(self):
        s=self.sample();s["quota"]["data"]["quotas"][0]["benefits"][0]["data_type"]="TEXT"
        with self.assertRaises(ValueError):m.normalize(s)
    def test_iso_expiry(self):
        self.assertEqual(m.expiry_epoch("2030-01-01T00:00:00+00:00"),1893456000)
    def test_milliseconds_expiry(self):
        self.assertEqual(m.expiry_epoch(1893456000000),1893456000)
