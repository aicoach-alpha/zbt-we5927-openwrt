import json
import pathlib
import subprocess
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE=ROOT/"source/veci-telco-indonesia"
PROVIDER=BASE/"files/usr/libexec/rpcd/veci.quota"
ACL=BASE/"files/usr/share/rpcd/acl.d/veci-quota.json"

class TelcoContract(unittest.TestCase):
    def test_shell_syntax(self):
        self.assertEqual(subprocess.run(["sh","-n",str(PROVIDER)]).returncode,0)
    def test_only_read_method_exposed(self):
        a=json.loads(subprocess.check_output(["sh",str(PROVIDER),"list"],text=True))
        self.assertEqual(a,{"status":{}})
        acl=json.loads(ACL.read_text())["veci-quota"]
        self.assertEqual(acl["read"]["ubus"]["veci.quota"],["status"])
        self.assertNotIn("write",acl)
    def test_no_unauthenticated_fake_quota(self):
        d=json.loads(subprocess.check_output(["sh",str(PROVIDER),"call","status"],text=True))
        self.assertEqual(d["provider"],"xl")
        self.assertEqual(d["state"],"not_connected")
        self.assertIsNone(d["remaining_bytes"])
        self.assertIsNone(d["total_bytes"])
        self.assertIsNone(d["used_bytes"])
        self.assertEqual(d["buckets"],[])
    def test_general_firmware_stays_unmodified(self):
        wf=(ROOT/".github/workflows/j8c-app-feed.yml").read_text()
        self.assertNotIn("set_module PACKAGE_veci-telco-indonesia",wf)
        cfg=(ROOT/"source/openwrt-we5927.config").read_text()
        self.assertNotIn("CONFIG_PACKAGE_veci-telco-indonesia=y",cfg)

if __name__=="__main__":
    unittest.main()
