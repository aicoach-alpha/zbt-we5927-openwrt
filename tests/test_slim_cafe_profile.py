import os
import pathlib
import subprocess
import tempfile
import unittest

import test_general_cafe_image_profile as profile
RESCUE=profile.RESCUE
EXCLUDED=profile.EXCLUDED
NEEDED=profile.NEEDED

ROOT=pathlib.Path(__file__).resolve().parents[1]
PROFILE=ROOT/'scripts/prepare-veci-general-cafe-profile.sh'
CANONICAL=ROOT/'source/openwrt-we5927.config'


class SlimCafeTests(unittest.TestCase):
    def test_source_excludes_duplicate_gui_and_wifi_debug_mesh(self):
        data=CANONICAL.read_text()
        for package in EXCLUDED:
            self.assertIn('# CONFIG_PACKAGE_'+package+' is not set',data)
            self.assertNotIn('CONFIG_PACKAGE_'+package+'=y',data)

    def test_preserves_rescue_luci_and_router_cafe_runtime(self):
        data=CANONICAL.read_text()
        for package in (*RESCUE,'veci','veci-default-ui',
                        'veci-app-catalog-we5927','veci-cellular-we5927',
                        'veci-update-we5927','kmod-mt7603','kmod-usb-net-rndis',
                        'kmod-usb-serial-option','luci-proto-ppp','luci-proto-ipv6'):
            self.assertIn('CONFIG_PACKAGE_'+package+'=y',data,package)

    def test_duplicate_manager_is_removed_but_apk_remains(self):
        source=CANONICAL.read_text()
        self.assertIn('# CONFIG_PACKAGE_luci-app-package-manager is not set',source)
        self.assertIn('CONFIG_PACKAGE_luci-base=y',source)
        self.assertIn('CONFIG_PACKAGE_luci-app-firewall=y',source)
        self.assertIn('CONFIG_PACKAGE_apk-mbedtls=y',source)
        catalog=ROOT/'source/veci-app-catalog-we5927/files/usr/libexec/rpcd/veci.apps'
        self.assertTrue(catalog.is_file())
        self.assertIn('apk ',catalog.read_text())

    def test_fails_closed_if_kconfig_resurrects_package_manager(self):
        with tempfile.TemporaryDirectory() as d:
            tree,env=profile.CafeProfileTests().fixture_tree(d)
            make=pathlib.Path(d)/'mockbin/make'
            make.write_text('#!/bin/sh\necho "CONFIG_PACKAGE_luci-app-package-manager=y" >> "$2/.config"\nexit 0\n')
            make.chmod(0o755)
            run=subprocess.run(['sh',str(PROFILE),str(tree)],env={**os.environ,**env},
                               capture_output=True,text=True,timeout=9)
            self.assertEqual(run.returncode,9,run.stderr)
            self.assertIn('redundant/unused',run.stderr)

    def test_savings_not_invented_without_measurement(self):
        script=PROFILE.read_text()
        self.assertNotIn('MEMORY_SAVED_MB=',script)
        self.assertNotIn('FLASH_SAVED_BYTES=',script)
        self.assertIn('SLIM_CAFE=',script)
        self.assertNotIn('sysupgrade -F',script)


if __name__=='__main__':
    unittest.main()
