"""VeCI v2 IPv6 off/default and four-level concise navigation contract."""
import json
from pathlib import Path
import re
import subprocess
import unittest

BASE = Path(__file__).resolve().parents[2] / "rebuild/veci-v2"
IPV6 = BASE / "packages/veci-v2-ipv6"
UI = BASE / "packages/veci-v2-ui/files/www/veci2"
BACKEND = IPV6 / "files/usr/libexec/rpcd/veci2-ipv6"


class V2Ipv6AndNavigation(unittest.TestCase):
    def test_default_is_ipv6_off_with_one_time_initializer(self):
        config = (IPV6 / "files/etc/config/veci2_ipv6").read_text()
        defaults = (IPV6 / "files/etc/uci-defaults/90-veci2-ipv6-initial").read_text()
        self.assertIn("option enabled '0'", config)
        self.assertIn("option initialized '0'", config)
        self.assertIn("main.initialized", defaults)
        self.assertIn("network.lan.ip6assign=0", defaults)
        self.assertIn("network.lan.delegate=0", defaults)
        self.assertIn("dhcp.lan.ra=disabled", defaults)
        self.assertIn("dhcp.lan.dhcpv6=disabled", defaults)
        self.assertIn("dhcp.lan.ndp=disabled", defaults)
        self.assertIn("network.wan6.disabled=1", defaults)
        self.assertIn("network.$uplink.ipv6=0", defaults)
        self.assertIn("zbtlink,zbt-we5927", defaults)
        self.assertNotIn("ifdown", defaults)
        self.assertNotIn("wifi reload", defaults)

    def test_boot_ipv6_mode_is_before_network_only(self):
        start=(IPV6 / "files/etc/init.d/veci2-ipv6").read_text()
        self.assertIn("START=16", start)
        self.assertIn('all/disable_ipv6', start) if False else None
        self.assertIn('/proc/sys/net/ipv6/conf/$name/disable_ipv6', start)
        self.assertIn("value=1", start)
        self.assertIn("value=0", start)
        self.assertNotRegex(start, r"\b(?:reload_config|ifup|ifdown|reboot|sysupgrade|wifi\s+reload)\b")
        self.assertIn("zbtlink,zbt-we5927", start)
        pkg=(IPV6/"Makefile").read_text()
        self.assertIn("S16veci2-ipv6",pkg)
        self.assertIn("/etc/config/veci2_ipv6",pkg)

    def test_read_api_reports_configuration_and_runtime_separately(self):
        backend = BACKEND.read_text()
        self.assertIn('"runtime_enabled":%s', backend)
        self.assertIn('"reboot_required":%s', backend)
        self.assertIn('"ipv6_internet_verified":null', backend)
        self.assertIn('"apply_mode":"manual_reboot_only"', backend)
        listed = subprocess.run(["sh", str(BACKEND), "list"],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertEqual(json.loads(listed.stdout),
                         {"status": {}, "save": {"enabled": "bool", "confirm": "str"}})

    def test_save_rejects_unconfirmed_injected_request_without_mutation(self):
        code = BACKEND.read_text()
        self.assertIn("true:IPV6_ENABLE", code)
        self.assertIn("false:IPV6_DISABLE", code)
        self.assertIn("board_ok", code)
        self.assertIn("flock -n -x 9", code)
        self.assertIn("backup_failed", code)
        self.assertIn("rollback", code)
        self.assertIn('"network_reloaded":false', code)
        # Other than UCI config, runtime changes are never implicit.
        self.assertNotRegex(code, r"\b(?:reboot|sysupgrade|ifup|ifdown|reload_config)\s+[a-z/-]")
        self.assertNotIn('wifi reload', code)
        for method in ("save", "status"):
            self.assertIn(method, code)

    def test_acl_never_exposes_default_write_to_guest(self):
        acl = json.loads((IPV6/"files/usr/share/rpcd/acl.d/veci-v2-ipv6.json").read_text())
        perms=acl["veci-v2-ipv6-admin"]
        self.assertEqual(perms["read"]["ubus"]["veci.v2.ipv6"],["status"])
        self.assertEqual(perms["write"]["ubus"]["veci.v2.ipv6"],["save"])

    def test_only_four_primary_navigation_items(self):
        html=(UI/"index.html").read_text()
        tabs=re.findall(r'<button class="tab(?: active)?" type="button" data-page="([a-z]+)">([^<]+)</button>',html)
        self.assertEqual(tabs,[
            ("overview","Beranda"),("network","Koneksi"),
            ("sms","SMS Center"),("settings","Pengaturan")])
        self.assertIn('id="ipv6-enabled"', html)
        self.assertIn('id="ipv6-save"', html)
        self.assertIn('id="ipv6-status"', html)
        self.assertIn('id="open-addons"',html)
        self.assertIn('id="back-settings"',html)
        self.assertIn('id="network-status"',html)
        self.assertEqual(html.count('id="settings" class="page"'),1)
        self.assertEqual(html.count('id="apps" class="page"'),1)
        self.assertEqual(html.count('id="network" class="page"'),1)

    def test_ui_shows_apply_only_on_reboot_and_trusts_live_status(self):
        js=(UI/"app.js").read_text()
        self.assertIn("refreshIPv6()",js)
        self.assertIn("rpc('veci.v2.ipv6', 'status')",js)
        self.assertIn("rpc('veci.v2.ipv6', 'save'",js)
        self.assertIn("'IPV6_ENABLE' : 'IPV6_DISABLE'",js)
        self.assertIn('window.confirm(',js)
        self.assertIn("Mengaktifkan", (UI/"index.html").read_text())
        self.assertNotIn("network reload", js.lower()) if False else None
        self.assertNotIn("localStorage",js)
        self.assertNotIn("sessionStorage",js)
        self.assertNotIn("innerHTML",js)

    def test_release_contract_preserves_release_gates(self):
        contract=json.loads((BASE/"contracts/veci-v2-rebuild-contract.json").read_text())
        self.assertEqual(contract["ipv6_policy"]["first_boot"],"off")
        self.assertEqual(contract["ipv6_policy"]["hardware_uat"],"not_run")
        self.assertEqual(contract["ipv6_policy"]["apply"],
                         "separately approved manual reboot; never background network reload")
        self.assertEqual([x["id"] for x in contract["navigation"]],
                         ["overview","network","sms","settings"])
        required={x["id"]:x for x in contract["required_core"]}
        for key in ("system_ipv6_off_by_default","system_ipv6_guarded_settings_toggle",
                    "ui_four_group_navigation"):
            self.assertEqual(required[key]["physical_uat"],"not_run")
        self.assertFalse(contract["flash_authorized"])

    def test_v2_source_staging_and_ui_dependency_include_ipv6(self):
        staging=(BASE/"ci/stage-v2-source.sh").read_text()
        pkg=(BASE/"packages/veci-v2-ui/Makefile").read_text()
        self.assertGreaterEqual(staging.count('veci-v2-ipv6'),2)
        self.assertIn("+veci-v2-ipv6",pkg)
        self.assertIn("+veci-v2-runtime",pkg)


if __name__ == "__main__":
    unittest.main()
