"""Fail-closed source-to-SquashFS image mapping for all 40 core features."""
import importlib.util
import pathlib
import shutil
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[2]
SOURCE=ROOT/"rebuild/veci-v2/ci/check-all-core-rom.py"
spec=importlib.util.spec_from_file_location("veci_full_rom",SOURCE)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CompleteRomSourceMap(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="veci-40-rom-test-")
        self.addCleanup(self.temp.cleanup)
        self.rom=pathlib.Path(self.temp.name)
        for pairs in module.FEATURES.values():
            for original,inside in pairs:
                destination=self.rom/inside
                destination.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(ROOT/original,destination)
    def test_40_sources_have_exact_compiled_image_path_and_bytes(self):
        self.assertEqual(len(module.FEATURES),40)
        self.assertEqual(module.check(self.rom),[])
    def test_any_missing_runtime_sends_fail_closed(self):
        target=self.rom/"usr/libexec/rpcd/veci.v2.observability"
        self.assertTrue(target.is_file())
        target.unlink()
        errors=module.check(self.rom)
        self.assertIn("ROM_MISSING_OR_WRONG_SIZE:firmware_24x7_observability:usr/libexec/rpcd/veci.v2.observability",errors)
    def test_modified_backend_rejected_even_same_bytes(self):
        target=self.rom/"usr/libexec/rpcd/veci.v2.firewall"
        payload=bytearray(target.read_bytes());payload[5]^=0x01
        target.write_bytes(payload)
        self.assertIn(
          "ROM_DIFFERENT_FROM_VERIFIED_SOURCE:firewall_zones_nat:usr/libexec/rpcd/veci.v2.firewall",
          module.check(self.rom))
    def test_luci_presence_hard_fail_and_no_hardware_claims(self):
        target=self.rom/"www/cgi-bin/luci"
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text("not allowed")
        self.assertIn("LUCI_PRESENT:www/cgi-bin/luci",module.check(self.rom))
        self.assertNotIn("hardware_uat=pass",SOURCE.read_text().lower())
    def test_cannot_substitute_feature_names(self):
        self.assertEqual(set(module.FEATURES),
                         {x["id"] for x in __import__("json").loads(module.CONTRACT.read_text())["required_core"]})

if __name__=="__main__":unittest.main()
