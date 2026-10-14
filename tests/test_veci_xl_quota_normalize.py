"""Native XL quota parser: only finite operator DATA benefits, no account fields leaked."""
import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"source/veci-telco-indonesia/veci-xl-quota-normalize.c"
BIN=Path(os.environ.get("VECI_XL_QUOTA_NORMALIZE_BIN","/tmp/veci-xl-quota-normalize-test"))

class XLQuotaNormalize(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  if not BIN.exists():raise AssertionError("native quota parser must be compiled")
 def call(self,obj):
  data=obj if isinstance(obj,str) else json.dumps(obj,separators=(',',':'))
  return subprocess.run([str(BIN)],input=data,capture_output=True,text=True,timeout=3)
 def test_data_only_and_no_sensitive_response_echo(self):
  o={"status":"SUCCESS","data":{"quotas":[
   {"name":"package1","benefits":[
     {"data_type":"DATA","remaining":500000000,"total":1000000000},
     {"data_type":"VOICE","remaining":1000000,"total":1200000},
     {"data_type":"TEXT","remaining":10,"total":100}]},
   {"benefits":[{"data_type":"DATA","remaining":1024000000,"total":2048000000}]}
  ]},"msisdn":"6281100000000","id_token":"UNSAFE_PRIVATE_SECRET"}
  p=self.call(o)
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
  out=json.loads(p.stdout)
  self.assertEqual(out,{"ok":True,"parsed_only":True,"provider":"xl",
                        "remaining_bytes":1524000000,"total_bytes":3048000000})
  for private in ("6281100000000","UNSAFE_PRIVATE_SECRET","VOICE","TEXT"):
   self.assertNotIn(private,p.stdout+p.stderr)
 def test_root_quotas_and_nested_quota_data_are_supported(self):
  benefit={"data_type":"data","remaining":"1","total":"4"}
  variants=[
   {"quotas":[{"benefits":[benefit]}]},
   {"data":{"quota":{"data":{"quotas":[{"benefits":[benefit]}]}}}},
   {"status":"OK","data":{"quotas":[{"benefits":[benefit]}]}}
  ]
  for v in variants:
   with self.subTest(v=v):
    r=self.call(v)
    self.assertEqual(r.returncode,0,r.stdout+r.stderr)
    self.assertEqual(json.loads(r.stdout)["remaining_bytes"],1)
 def test_never_infer_from_offers_or_unknown_shapes(self):
  cases=[
   {},{"status":"FAILED","data":{"quotas":[{"benefits":[{"data_type":"DATA","remaining":1,"total":2}]}]}},
   {"data":{"packages":[{"benefits":[{"data_type":"DATA","remaining":1,"total":2}]}]}},
   {"quota_display":"Sisa Kuota 10GB"},
   {"quotas":[]},
   {"quotas":[{"benefits":[{"data_type":"VOICE","remaining":50,"total":100}]}]},
   {"quotas":[{"benefits":[{"data_type":"DATA","remaining":100,"total":50}]}]},
   {"quotas":[{"benefits":[{"data_type":"DATA","remaining":-1,"total":2}]}]},
   {"quotas":[{"benefits":[{"data_type":"DATA","remaining":1.5,"total":2}]}]},
   {"quotas":[{"benefits":[{"data_type":"DATA","remaining":1,"total":"unlimited"}]}]},
   {"quotas":[{"benefits":[{"data_type":"DATA","remaining":99999999999999,"total":99999999999999}]}]},
   {"quotas":[{"benefits":[{"data_type":"DATA","remaining":2,"remaining":1,"total":3}]}]}
  ]
  for v in cases:
   with self.subTest(v=v):
    p=self.call(v)
    self.assertNotEqual(p.returncode,0,p.stdout+p.stderr)
    self.assertFalse(json.loads(p.stdout)["ok"])
 def test_unlimited_skipped_not_finite(self):
  o={"data":{"quotas":[{"benefits":[
    {"data_type":"DATA","is_unlimited":True,"remaining":0,"total":0},
    {"data_type":"DATA","remaining":150,"total":500}]}]}}
  p=self.call(o)
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
  self.assertEqual(json.loads(p.stdout)["remaining_bytes"],150)
 def test_duplicate_keys_cannot_override_quota(self):
  payload='{"quotas":[{"benefits":[{"data_type":"DATA","remaining":50,"remaining":5,"total":100}]}]}'
  p=self.call(payload)
  self.assertNotEqual(p.returncode,0)
  self.assertEqual(json.loads(p.stdout)["reason"],"invalid_quota_payload")
 def test_bounded_response_and_deep_payload_refused(self):
  p=self.call("{"+" "*66000+"}")
  self.assertNotEqual(p.returncode,0)
  self.assertNotIn(" ",p.stdout)
  deep='['*27+'0'+']'*27
  p=self.call('{"data":{"quotas":'+deep+'}}')
  self.assertNotEqual(p.returncode,0)
 def test_raw_secret_not_logged(self):
  raw='{"auth_token":"SECRET_DO_NOT_PRINT","quota":"invalid"}'
  p=self.call(raw)
  self.assertNotEqual(p.returncode,0)
  self.assertNotIn("SECRET_DO_NOT_PRINT",p.stdout+p.stderr)
 def test_no_carrier_network_code(self):
  s=SOURCE.read_text()
  for x in ("api.myxl", "AT+CM", "https://", "curl ", "wget ", "system(", "exec("):
   self.assertNotIn(x,s)

if __name__=="__main__":unittest.main()
