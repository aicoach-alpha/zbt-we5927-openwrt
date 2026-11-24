"""Owner's exact OEM hardware contract; lab/source checks, never a boot test."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "rebuild/veci-v2"
PROFILE = json.loads((BASE / "contracts/owner-oem-physical-20261119.json").read_text())
V2 = json.loads((BASE / "contracts/veci-v2-rebuild-contract.json").read_text())


class OwnerOemBaselineTests(unittest.TestCase):
    def test_hardware_exactness_and_no_false_5g(self):
        self.assertEqual(PROFILE["board"], "zbtlink,zbt-we5927")
        self.assertEqual(PROFILE["firmware_mtd_bytes"], 0x7a0000)
        self.assertEqual(PROFILE["firmware_mtd_erase_bytes"], 0x10000)
        self.assertEqual(PROFILE["oem_verified"]["wifi_2g_interface"], "ra0")
        self.assertIs(PROFILE["oem_verified"]["wifi_5g_present"], False)
        self.assertEqual(PROFILE["owner_firmware_parity"]["wifi_5g"], "not_supported_by_hardware")
        self.assertIs(PROFILE["oem_verified"]["sim_web_slot_to_gpio_verified"], False)
        self.assertEqual(PROFILE["oem_verified"]["sim_selector_gpio"], 46)

    def test_exact_oem_identity_without_personal_data(self):
        self.assertEqual(PROFILE["vendor_image_sha256"], V2["oem_sha256"])
        self.assertEqual(PROFILE["oem_verified"]["usb_modem_vidpid"], "05c6:902e")
        self.assertEqual(PROFILE["oem_verified"]["lte_device"], "usb0")
        raw = (BASE / "contracts/owner-oem-physical-20261119.json").read_text().lower()
        for forbidden in ("iccid", "imei", "imsi", "password", "pin_code", "msisdn"):
            self.assertNotIn('"' + forbidden + '":', raw)

    def test_openwrt_pin_gui_and_sms_are_packaged(self):
        self.assertEqual(PROFILE["new_build"]["openwrt"], V2["openwrt_version"])
        self.assertEqual(PROFILE["new_build"]["kernel"], V2["kernel_version"])
        self.assertIs(PROFILE["new_build"]["luci_allowed"], False)
        config = (ROOT / "source/openwrt-we5927.config").read_text()
        self.assertIn("CONFIG_TARGET_ramips_mt76x8_DEVICE_zbtlink_zbt-we5927=y", config)
        self.assertIn("CONFIG_PACKAGE_kmod-usb-net-rndis=y", config)
        self.assertIn("CONFIG_PACKAGE_dnsmasq=y", config)
        ui = (BASE / "packages/veci-v2-ui/files/www/veci2/index.html").read_text()
        package = (BASE / "packages/veci-v2-ui/Makefile").read_text()
        self.assertIn('data-page="sms"', ui)
        self.assertIn("SMS Center", ui)
        self.assertIn("+veci-v2-sms", package)
        self.assertIn("+veci-v2-runtime", package)
        self.assertNotIn("+luci", package)
        self.assertNotIn("CONFIG_PACKAGE_luci=y", config)

    def test_laboratory_is_not_owner_flash_approval(self):
        self.assertIs(PROFILE["new_build"]["live_flash_allowed"], False)
        self.assertEqual(PROFILE["new_build"]["sms_physical_uat"], "not_run")
        self.assertIs(PROFILE["oem_verified"]["speedtest_dns_functional_uat"], False)
        self.assertEqual(V2["release_state"], "DEVELOPMENT_NOT_FLASHABLE")
        self.assertIs(V2["flash_authorized"], False)


if __name__ == "__main__":
    unittest.main()
