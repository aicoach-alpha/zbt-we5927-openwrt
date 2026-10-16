import json
import pathlib
import subprocess
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE=ROOT/"source/veci-telco-indonesia"
PROVIDER=BASE/"files/usr/libexec/rpcd/veci.quota"
ACL=BASE/"files/usr/share/rpcd/acl.d/veci-quota.json"
REGISTRY=BASE/"files/usr/share/veci/telco/providers.json"
CACHE_HELPER=BASE/"files/usr/libexec/veci-quota-cache"

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
        with tempfile.TemporaryDirectory() as root:
            # No cache file -> no quota. Provider always uses its fixed local path.
            d=json.loads(subprocess.check_output([
                "sh",str(CACHE_HELPER),"status",str(pathlib.Path(root)/"not-created.json")
            ],text=True))
        self.assertEqual(d["provider"],"xl")
        self.assertEqual(d["state"],"not_connected")
        self.assertIsNone(d["remaining_bytes"])
        self.assertIsNone(d["total_bytes"])
        self.assertIsNone(d["used_bytes"])
        self.assertEqual(d["buckets"],[])
        self.assertIn("/usr/libexec/veci-quota-cache status /tmp/veci-telco/quota-xl.json",PROVIDER.read_text())
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
        self.assertIn("veci-quota-cache",pkg)
        self.assertIn("DEPENDS:=+rpcd +luci-base +jsonfilter",pkg)
        self.assertNotIn("DEPENDS:=+veci",pkg)
        self.assertIn("PKG_VERSION:=0.2.1",pkg)

        self.assertIn("luci-app-veci-quota.json",pkg)
        self.assertIn("view/veci/quota.js",pkg)
    def test_standalone_public_edition_contract(self):
        spec=(ROOT/"docs/VECI-INDONESIA-EDITION.md").read_text()
        pkg=(BASE/"Makefile").read_text()
        self.assertIn("Standalone mode — mandatory release gate",spec)
        self.assertIn("No central VeCI backend",spec)
        self.assertIn("Direct-to-carrier egress only",spec)
        self.assertIn("No always-on provider processes",spec)
        self.assertIn("no developer-hosted companion",pkg)
        self.assertNotIn("requires a separately authenticated companion adapter",pkg.lower())
        backend=PROVIDER.read_text()
        self.assertNotIn("curl ",backend)
        self.assertNotIn("wget ",backend)
        self.assertNotIn("https://",backend)
        # Initial skeleton neither pretends to authenticate nor reports fake quota.
        self.assertIn("veci-quota-cache status",backend)
    def test_edition_build_selector_isolated(self):
        script=ROOT/"scripts/select-veci-edition.sh"
        with tempfile.TemporaryDirectory() as t:
            tree=pathlib.Path(t)
            config=tree/".config"
            config.write_text("CONFIG_PACKAGE_veci=y\n")
            general=subprocess.run(["sh",str(script),"general",str(config)],capture_output=True,text=True)
            self.assertEqual(general.returncode,0,general.stderr)
            self.assertIn("# CONFIG_PACKAGE_veci-telco-indonesia is not set",config.read_text())
            self.assertNotIn("CONFIG_PACKAGE_veci-telco-indonesia=y",config.read_text())
            # Indonesia must not silently succeed if package staging was skipped.
            missing=subprocess.run(["sh",str(script),"indonesia",str(config)],capture_output=True,text=True)
            self.assertNotEqual(missing.returncode,0)
            pkg=tree/"package/veci-telco-indonesia"
            pkg.mkdir(parents=True)
            (pkg/"Makefile").write_text("fake staging fixture")
            native_pkg=tree/"package/veci-telco-xl-native"
            native_pkg.mkdir(parents=True)
            (native_pkg/"Makefile").write_text("optional native fixture")
            indonesia=subprocess.run(["sh",str(script),"indonesia",str(config)],capture_output=True,text=True)
            self.assertEqual(indonesia.returncode,0,indonesia.stderr)
            self.assertEqual(config.read_text().count("CONFIG_PACKAGE_veci-telco-indonesia=y"),1)
            self.assertEqual(config.read_text().count("# CONFIG_PACKAGE_veci-telco-xl-native is not set"),1)
            self.assertNotIn("CONFIG_PACKAGE_veci-telco-xl-native=y",config.read_text())
            cannot_general=subprocess.run(["sh",str(script),"general",str(config)],capture_output=True,text=True)
            self.assertNotEqual(cannot_general.returncode,0)
            invalid=subprocess.run(["sh",str(script),"unknown",str(config)],capture_output=True,text=True)
            self.assertNotEqual(invalid.returncode,0)
    def test_preparation_does_not_install_edition_implicitly(self):
        script=(ROOT/"scripts/prepare-veci.sh").read_text()
        self.assertIn('VECI_EDITION="${VECI_EDITION:-general}"',script)
        self.assertIn('if [ "$VECI_EDITION" = "indonesia" ]',script)
        self.assertIn('"edition": "$VECI_EDITION"',script)
    def test_general_firmware_stays_unmodified(self):
        wf=(ROOT/".github/workflows/j8c-app-feed.yml").read_text()
        self.assertNotIn("set_module PACKAGE_veci-telco-indonesia",wf)
        cfg=(ROOT/"source/openwrt-we5927.config").read_text()
        self.assertNotIn("CONFIG_PACKAGE_veci-telco-indonesia=y",cfg)

if __name__=="__main__":
    unittest.main()
