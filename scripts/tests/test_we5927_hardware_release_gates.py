"""Exact WE2825-2SIM board release checks; no physical-UAT claims."""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[2]
def read(name):
    return (ROOT/name).read_text(encoding="utf-8")
PATCH=read("source/openwrt-zbt-we5927-current.patch")
CONFIG=read("source/openwrt-we5927.config")
PIN=read("source/openwrt-source-commit.txt").strip()
VERSION="25.12.6"
MTD_SIZE=7995392

class HardwareReleaseIdentity(unittest.TestCase):
    def test_upstream_pin_is_identical_in_all_active_builds(self):
        self.assertEqual(PIN,"64900e756efa667774214f9c6b17c113222e01f7")
        self.assertRegex(PIN,r"^[0-9a-f]{40}$")
        for name in (
            ".github/workflows/veci-reliability-full-image-rc.yml",
            ".github/workflows/veci-reliability-integration.yml",
            ".github/workflows/veci-mt7603-crossbuild.yml",
        ):
            with self.subTest(file=name):
                self.assertIn(PIN,read(name))
                self.assertNotIn("f0a60eee2fe051741c643ea6118718aae1ef17fb",read(name))
        for name in ("scripts/veci_release_evidence.py","scripts/veci_release_manifest.py",
                     "scripts/verify_veci_image.py","scripts/stage-veci-reliability-rc.sh",
                     "scripts/finalize-sysupgrade.sh"):
            self.assertIn(VERSION,read(name),name)

    def test_no_similar_model_or_flash_variant_substitution(self):
        self.assertIn('compatible = "zbtlink,zbt-we5927", "mediatek,mt7628an-soc";',PATCH)
        self.assertIn('model = "Zbtlink ZBT-WE5927";',PATCH)
        self.assertIn('reg = <0x50000 0x7a0000>;',PATCH)
        self.assertIn('reg = <0x7f0000 0x10000>;',PATCH)
        self.assertIn('reg = <0x40000 0x10000>;',PATCH)
        # u-boot 0x30000, env 0x10000, factory 0x10000,
        # firmware 0x7a0000, art 0x10000; no NAND assumptions.
        self.assertEqual(sum([0x30000,0x10000,0x10000,0x7a0000,0x10000]),0x800000)
        self.assertEqual(MTD_SIZE,0x7a0000)
        self.assertIn("IMAGE_SIZE := 7808k",PATCH)
        self.assertIn("TARGET_DEVICES += zbtlink_zbt-we5927",PATCH)
        self.assertIn("CONFIG_TARGET_ramips_mt76x8_DEVICE_zbtlink_zbt-we5927=y",CONFIG)
        self.assertIn("CONFIG_TARGET_ROOTFS_SQUASHFS=y",CONFIG)
        self.assertIn("# CONFIG_TARGET_ROOTFS_EROFS is not set",CONFIG)

    def test_gpio_radio_eeprom_and_eth_are_board_specific(self):
        for snippet in (
            "gpios = <&gpio 1 GPIO_ACTIVE_HIGH>;",
            "gpios = <&gpio 46 GPIO_ACTIVE_LOW>;",
            "gpios = <&gpio 37 GPIO_ACTIVE_HIGH>;",
            "nvmem-cells = <&eeprom_factory_0>;",
            "nvmem-cells = <&macaddr_factory_28>;",
            "status = \"okay\";",
        ):
            self.assertIn(snippet,PATCH,snippet)
        self.assertIn('reg = <0x0 0x400>;',PATCH)
        self.assertIn('reg = <0x28 0x6>;',PATCH)
        self.assertIn("CONFIG_PACKAGE_kmod-mt7603=y",CONFIG)
        self.assertIn("CONFIG_PACKAGE_wpad-basic-mbedtls=y",CONFIG)
        self.assertIn("CONFIG_PACKAGE_kmod-usb-net-rndis=y",CONFIG)
        self.assertIn("CONFIG_PACKAGE_dnsmasq=y",CONFIG)
        self.assertIn("CONFIG_PACKAGE_firewall4=y",CONFIG)
        self.assertIn("CONFIG_PACKAGE_uhttpd=y",CONFIG)

    def test_modem_identity_in_firmware_is_rndis_not_guessed_qmi(self):
        cfg=read("source/we5927-lte/files/etc/config/we5927_lte")
        lte=read("source/we5927-lte/files/usr/sbin/we5927-lte")
        self.assertIn("option usb_vid '05c6'",cfg)
        self.assertIn("option usb_pid '902e'",cfg)
        self.assertIn("option data_if 'usb0'",cfg)
        self.assertIn("option at_port '/dev/ttyUSB2'",cfg)
        self.assertIn("USB interface 1.4",lte)
        self.assertIn("ttyUSB3 is function 1.5",lte)
        self.assertIn("flock -n",lte)
        hot=read("source/we5927-lte/files/etc/hotplug.d/usb/30-we5927-lte")
        self.assertNotRegex("\n".join(line for line in hot.splitlines()
                                      if not line.strip().startswith("#")),
                            r"\b(?:ifup|ifdown|power_cycle|wifi\s+reload)\b")

    def test_only_one_native_ui_and_optional_guest(self):
        self.assertIn("# CONFIG_DEFAULT_luci is not set",CONFIG)
        self.assertIn("CONFIG_PACKAGE_veci=y",
                      read(".github/workflows/veci-reliability-full-image-rc.yml"))
        workflow=read(".github/workflows/veci-reliability-full-image-rc.yml")
        self.assertIn("! grep -Fxq 'CONFIG_PACKAGE_veci-app-guest=y'",workflow)
        self.assertIn("! grep -Fxq 'CONFIG_PACKAGE_veci-data-meter=y'",workflow)
        self.assertIn("GATE_NO_LUCI_RUNTIME_PASS",workflow)
        self.assertIn("FLASH_PERMISSION=NO",workflow)
        self.assertIn("MIN_FIRMWARE_HEADROOM_BYTES=1048576",workflow)

    def test_guardian_is_observe_only_and_update_default_off(self):
        guardian=read("source/veci-wifi-guardian/veci-wifi-guardian")
        init=read("source/we5927-lte/files/etc/init.d/we5927-lte")
        startup=read("source/veci-update-we5927/files/etc/uci-defaults/96-veci-update-we5927")
        self.assertIn("auto_recover=0",guardian)
        lines="\n".join(line for line in guardian.splitlines()
                        if not line.lstrip().startswith("#"))
        self.assertNotRegex(lines,r"\bwifi\s+(?:up|down|reload)\b")
        self.assertIn("procd_add_reload_trigger we5927_lte\n",init)
        self.assertNotIn("procd_add_reload_trigger we5927_lte network",init)
        self.assertIn("veci.update.auto_install='0'",startup)
        self.assertIn("veci.update.auto_download='0'",startup)

if __name__ == "__main__":
    unittest.main()
