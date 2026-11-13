"""Offline release policy: guest/voucher are installable apps, not ROM payload."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
STAGER = (ROOT / "scripts/stage-veci-reliability-rc.sh").read_text()
BUILD = (ROOT / ".github/workflows/veci-reliability-full-image-rc.yml").read_text()

class OptionalAppsPolicyTests(unittest.TestCase):
    def test_optional_not_selected(self):
        self.assertIn("! grep -Fxq 'CONFIG_PACKAGE_veci-app-guest=y'", BUILD)
        self.assertIn("! grep -Fxq 'CONFIG_PACKAGE_veci-app-voucher=y'", BUILD)

    def test_catalog_lists_optional_apps(self):
        for name in ("guest", "voucher"):
            self.assertTrue((ROOT / "source/veci-app-catalog-we5927/files/usr/share/veci/apps" / (name+".json")).is_file())

    def test_base_packages_bundled(self):
        for pkg in ("veci", "veci-default-ui", "veci-cellular-we5927",
                    "veci-app-catalog-we5927", "veci-update-we5927"):
            self.assertIn("CONFIG_PACKAGE_"+pkg+"=y", BUILD)

    def test_sms_send_dep_is_built(self):
        make=(ROOT/"source/we5927-lte/Makefile").read_text()
        self.assertIn("veci-sms-cmgs.c", make)
        self.assertIn("$(PKG_BUILD_DIR)/veci-sms-cmgs", make)
        self.assertIn("test -x \"$rdir/usr/libexec/veci-sms-cmgs\"", BUILD)

    def test_runtime_binary_exclusion(self):
        self.assertIn("OPTIONAL_GUEST_VOUCHER_NOT_BUNDLED=PASS", BUILD)
        self.assertIn("GUEST_VOUCHER_OPTIONAL_NOT_BUNDLED=PASS", STAGER)

if __name__ == "__main__":
    unittest.main()
