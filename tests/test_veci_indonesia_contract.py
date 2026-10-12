import json
import pathlib
import subprocess
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE=ROOT/"source/veci-telco-indonesia"
PROVIDER=BASE/"files/usr/libexec/rpcd/veci.quota"
ACL=BASE/"files/usr/share/rpcd/acl.d/veci-quota.json"
REGISTRY=BASE/"files/usr/share/veci/telco/providers.json"

class TelcoContract(unittest.TestCase):
    def test_shell_syntax(self):
        self.assertEqual(subprocess.run(["sh","-n",str(PROVIDER)]).returncode,0)
    def test_only_read_method_exposed(self):
        a=json.loads(subprocess.check_output(["sh",str(PROVIDER),"list"],text=True))
        self.assertEqual(a,{"status":{},"providers":{}})
        acl=json.loads(ACL.read_text())["veci-quota"]
        self.assertEqual(acl["read"]["ubus"]["veci.quota"],["status","providers"])
        self.assertNotIn("write",acl)
    def test_no_unauthenticated_fake_quota(self):
        d=json.loads(subprocess.check_output(["sh",str(PROVIDER),"call","status"],text=True))
        self.assertEqual(d["provider"],"xl")
        self.assertEqual(d["state"],"not_connected")
        self.assertIsNone(d["remaining_bytes"])
        self.assertIsNone(d["total_bytes"])
        self.assertIsNone(d["used_bytes"])
        self.assertEqual(d["buckets"],[])
    def test_single_registry_has_major_brands(self):
        reg=json.loads(REGISTRY.read_text())
        self.assertEqual(reg["edition"],"indonesia")
        providers={p["id"]:p for p in reg["providers"]}
        self.assertTrue({"xl","axis","smartfren","telkomsel","byu","im3","tri"}.issubset(providers))
        self.assertEqual(len(providers),len(reg["providers"]))
        families={f["id"]:set(f["brands"]) for f in reg["families"]}
        for p in reg["providers"]:
            self.assertEqual(p["status"],"not_implemented")
            self.assertIn(p["family"],families)
            self.assertIn(p["id"],families[p["family"]])
            self.assertFalse(p.get("connected",False))
        self.assertEqual(providers["xl"]["shared_lib"],providers["axis"]["shared_lib"])
        self.assertEqual(providers["im3"]["shared_lib"],providers["tri"]["shared_lib"])
        self.assertNotEqual(providers["telkomsel"]["engine"],providers["byu"]["engine"])
        self.assertNotEqual(providers["xl"]["engine"],providers["smartfren"]["engine"])
    def test_registry_is_explicit_read_only(self):
        self.assertIn("providers)",PROVIDER.read_text())
        self.assertIn("providers.json",PROVIDER.read_text())
        self.assertNotIn("refresh_token",REGISTRY.read_text().lower())
        self.assertNotIn("access_token",REGISTRY.read_text().lower())
        self.assertNotIn('"otp"',REGISTRY.read_text().lower())
        self.assertNotIn("signing_key",REGISTRY.read_text().lower())
        pkg=(BASE/"Makefile").read_text()
        self.assertIn("providers.json",pkg)
        self.assertNotIn("python3",pkg.lower())
        self.assertNotIn("nodejs",pkg.lower())
    def test_general_firmware_stays_unmodified(self):
        wf=(ROOT/".github/workflows/j8c-app-feed.yml").read_text()
        self.assertNotIn("set_module PACKAGE_veci-telco-indonesia",wf)
        cfg=(ROOT/"source/openwrt-we5927.config").read_text()
        self.assertNotIn("CONFIG_PACKAGE_veci-telco-indonesia=y",cfg)

if __name__=="__main__":
    unittest.main()
