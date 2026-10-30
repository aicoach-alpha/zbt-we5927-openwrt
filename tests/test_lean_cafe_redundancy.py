import pathlib, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
CFG=ROOT/'source/openwrt-we5927.config'
PROFILE=ROOT/'scripts/prepare-veci-general-cafe-profile.sh'
class LeanCafeTests(unittest.TestCase):
    def test_no_full_luci_collection_or_duplicate_manager_in_baseline(self):
        data=CFG.read_text()
        self.assertIn('# CONFIG_PACKAGE_luci is not set',data)
        self.assertIn('# CONFIG_PACKAGE_luci-app-package-manager is not set',data)
        self.assertIn('CONFIG_PACKAGE_luci-light=y',data)
    def test_modem_and_network_recovery_stay_intact(self):
        data=CFG.read_text()
        for package in ('we5927-lte','veci','veci-default-ui','veci-cellular-we5927',
                        'veci-app-catalog-we5927','veci-update-we5927',
                        'kmod-usb-net-rndis','luci-light','ppp','ppp-mod-pppoe',
                        'odhcpd-ipv6only'):
            self.assertIn('CONFIG_PACKAGE_'+package+'=y',data,package)
    def test_profile_does_not_strip_uspot_bpf_dependencies(self):
        text=PROFILE.read_text()
        for package in ('uspot','uspot-www','veci-app-guest','veci-app-voucher'):
            self.assertIn(package,text)
        for forbidden in ('kmod-sched-bpf','ucode-mod-bpf','libbpf'):
            self.assertNotIn("disabled=('"+forbidden,text)
    def test_profile_explicitly_fails_if_luci_is_reselected(self):
        text=PROFILE.read_text()
        self.assertIn('luci luci-app-package-manager',text)
        self.assertIn('redundant LuCI collection/package-manager was reselected',text)
if __name__=='__main__': unittest.main()
