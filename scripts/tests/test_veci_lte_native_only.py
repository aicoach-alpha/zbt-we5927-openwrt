"""Regress the hidden LuCI install from the WE5927 LTE board package."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class LteNativeOnlyTests(unittest.TestCase):
    def test_board_patch_no_longer_forces_luci(self):
        patch = (ROOT / "source/openwrt-zbt-we5927-current.patch").read_text()
        self.assertIn("DEVICE_PACKAGES := we5927-lte", patch)
        self.assertNotIn("DEVICE_PACKAGES := luci we5927-lte", patch)
        self.assertNotIn("DEPENDS:=+luci-base", patch)

    def test_runtime_lte_package_does_not_install_luci_resources(self):
        pkg = (ROOT / "source/we5927-lte/Makefile").read_text()
        for forbidden in ("+luci-base", "luci-static", "luci-app-we5927-lte",
                          "/usr/share/luci"):
            self.assertNotIn(forbidden, pkg)
        self.assertIn("veci-sms-cmgs", pkg)
        self.assertIn("we5927-at", pkg)
        self.assertIn("30-we5927-lte", pkg)
        self.assertFalse((ROOT / "source/we5927-lte/files/www/luci-static").exists())
        self.assertFalse((ROOT / "source/we5927-lte/files/usr/share/luci").exists())

    def test_staging_refuses_resurrected_luci(self):
        source = (ROOT / "scripts/stage-veci-reliability-rc.sh").read_text()
        self.assertIn("native_only_lte_package_still_installs_luci", source)
        self.assertIn("native_only_device_profile_still_selects_luci", source)
        self.assertIn("NO_LEGACY_LUCI_LTE_DEPENDENCIES=PASS", source)

    def test_ci_failed_native_check_is_identifiable(self):
        workflow = (ROOT / ".github/workflows/veci-reliability-full-image-rc.yml").read_text()
        self.assertIn("LEGACY_LUCI_CONTENT_PRESENT=", workflow)
        self.assertIn("NATIVE_FIRMWARE_VERIFY_FAILED", workflow)
        self.assertIn("GATE_NO_LUCI_RUNTIME_PASS", workflow)
        self.assertIn("veci-we5927-DEBUG-NOT-FLASH-", workflow)


if __name__ == "__main__":
    unittest.main()
