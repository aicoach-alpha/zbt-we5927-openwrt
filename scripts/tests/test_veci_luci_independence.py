import importlib.util
import pathlib
import tempfile
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "check-veci-luci-independence.py"
spec = importlib.util.spec_from_file_location("luci_gate", SOURCE)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

class MigrationGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        for p in gate.REQUIRED_PATHS:
            dest = self.root / p
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.touch()

    def tearDown(self):
        self.tmp.cleanup()

    def test_minimal_firmware_passes(self):
        self.assertEqual([], gate.evaluate(self.root, ["uhttpd", "rpcd", "ubus"]))

    def test_luci_package_fails(self):
        self.assertIn("luci_package_present:luci-base",
                      gate.evaluate(self.root, ["luci-base"]))

    def test_luci_assets_fail(self):
        p = self.root / "www/luci-static"
        p.mkdir(parents=True)
        self.assertIn("legacy_ui_path_present:www/luci-static",
                      gate.evaluate(self.root, []))

    def test_reference_fails(self):
        p = self.root / "www/index.html"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('<a href="/cgi-bin/luci">bad</a>')
        self.assertIn("legacy_ui_reference:www/index.html",
                      gate.evaluate(self.root, []))

    def test_runtime_dependency_fails(self):
        (self.root / gate.REQUIRED_PATHS[0]).unlink()
        self.assertIn("required_runtime_missing:" + gate.REQUIRED_PATHS[0],
                      gate.evaluate(self.root, []))

    def test_missing_root_fails(self):
        self.assertEqual(["staged_rootfs_missing"],
                         gate.evaluate(self.root / "missing", []))

if __name__ == "__main__":
    unittest.main()
