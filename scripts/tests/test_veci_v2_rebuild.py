"""Rebuild-v2 safety and truthful runtime contracts, independent of router."""
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "rebuild/veci-v2"
STATUS = (BASE / "packages/veci-v2-runtime/veci2-status").read_text()
PKGS = (BASE / "packages/veci-v2-package-manager/veci2-apk").read_text()
OEM = json.loads((BASE / "contracts/oem-we5927-2sim.json").read_text())


def ash(code):
    p = subprocess.run(["sh", "-c", code], capture_output=True, text=True, timeout=8)
    return p


def without_main(code):
    suffix = 'main "$@"'
    assert code.rstrip().endswith(suffix)
    return code.rsplit(suffix, 1)[0]


class V2BuildTests(unittest.TestCase):
    def test_oem_is_exact_dualsim_original_binary_evidence(self):
        self.assertEqual(OEM["vendor_model"], "ZBT-WE5927-DSIM")
        self.assertEqual(OEM["vendor_display_model"], "WE2825-2SIM")
        self.assertEqual(OEM["vendor_release"], "26.08.09")
        self.assertEqual(OEM["source_image_bytes"], 7471108)
        self.assertEqual(OEM["source_sha256"],
                         "80529b8e9c31d686eb7f63a1517d6dbcf781f26cb4aceb7b8b1ff27c2d51d1f9")
        self.assertEqual(OEM["vendor_watchdog_gpio_source"], 37)
        self.assertEqual(sum(v is True for category in OEM["menu_flags"].values()
                             for v in category.values()), 20)
        self.assertEqual(sum(v is False for category in OEM["menu_flags"].values()
                             for v in category.values()), 13)
        self.assertFalse(OEM["menu_flags"]["wifi"]["wifi_5"])
        self.assertTrue(OEM["menu_flags"]["net"]["net_cellular1"])
        self.assertFalse(OEM["menu_flags"]["net"]["net_cellular2"])
        self.assertNotIn("password", OEM)
        self.assertNotIn("imei", OEM)
        self.assertNotIn("ssid", OEM)

    def test_oem_inventory_only_allows_non_sensitive_config_fields(self):
        src = (BASE / "oem_inventory.py").read_text()
        self.assertIn("WHITELIST", src)
        self.assertIn("MODEL = \"ZBT-WE5927-DSIM\"", src)
        self.assertNotIn("password\",", src)
        self.assertNotIn("imei\",", src)
        self.assertNotIn("ssid\",", src)
        self.assertIn("hashlib.sha256", src)

    def test_status_contract_detects_missing_bss_and_never_infers_internet(self):
        stub = """
live_board() { echo zbtlink,zbt-we5927; }
openwrt_version() { echo 25.12.6; }
ubus_radio_up() { echo true; }
ubus_hostapd_ap() { return 1; }
lte_data_device() { echo usb0; }
ip() {
  case "$*" in
    *'addr show dev usb0'*) echo '12: usb0 inet 198.51.100.12/24' ;;
    *'route show default dev usb0'*) echo 'default via 198.51.100.1 dev usb0' ;;
  esac
}
pidof() { echo 1712; }
df() { printf 'Filesystem 1024-blocks Used Available Capacity Mounted\\n/dev/overlay 8192 1024 7168 14%% /overlay\\n'; }
awk() { printf '16384\\n'; }
main call status
"""
        p = ash(without_main(STATUS) + stub)
        self.assertEqual(p.returncode, 0, p.stderr)
        j = json.loads(p.stdout)
        self.assertTrue(j["board_supported"])
        self.assertTrue(j["openwrt_supported"])
        self.assertTrue(j["lte_ipv4"])
        self.assertTrue(j["lte_default_route"])
        self.assertIsNone(j["internet_verified"])
        self.assertTrue(j["wifi_radio_config_up"])
        self.assertFalse(j["wifi_ap_enabled"])
        self.assertTrue(j["wifi_ap_missing"])
        self.assertIsNone(j["wifi_beacon_verified"])
        self.assertEqual(j["netifd_count"], 1)
        self.assertNotIn("imei", p.stdout.lower())

    def test_lte_link_checks_only_the_active_managed_device(self):
        stubs = """
uci() { [ "$*" = '-q get we5927_lte.main.data_if' ] && echo usb1; }
ubus() { [ "$5" = network.interface.lte ] && echo "$active"; }
jsonfilter() { [ "$2" = '@.l3_device' ] && cat; }
ip() {
  case "$*" in
    '-4 -o addr show dev usb1') echo '3: usb1 inet 192.0.2.2/24' ;;
    '-4 route show default dev usb1') echo 'default via 192.0.2.1 dev usb1' ;;
    *) echo unexpected-ip-query >&2 ;;
  esac
}
ubus_radio_up() { :; }
ubus_hostapd_ap() { :; }
"""
        for active, expected in [('usb1', True), ('usb0', None), ('', None)]:
            with self.subTest(active=active):
                reply = ash(without_main(STATUS) + stubs + f"active='{active}'\nmain call status")
                self.assertEqual(reply.returncode, 0, reply.stderr)
                data = json.loads(reply.stdout)
                self.assertIs(data['lte_ipv4'], expected)
                self.assertIs(data['lte_default_route'], expected)
                self.assertIsNone(data['internet_verified'])
                self.assertNotIn('192.0.2.', reply.stdout)

    def test_ap_status_uses_present_radio_interfaces(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "office-ap/phy80211").mkdir(parents=True)
            code = without_main(STATUS).replace("/sys/class/net/", directory + "/")
            stubs = """
jsonfilter() { cat; }
ubus() {
  case "$5" in
    network.wireless) printf '%s\\n' stale-ap office-ap ;;
    hostapd.stale-ap) echo ENABLED ;;
    hostapd.office-ap) echo ENABLED ;;
  esac
}
ubus_hostapd_ap
"""
            self.assertEqual(ash(code + stubs).stdout.strip(), "ENABLED")
            (root / "office-ap/phy80211").rmdir()
            self.assertNotEqual(ash(code + stubs).returncode, 0)

    def test_ethernet_reads_only_external_switch_ports(self):
        stub = """
live_board() { echo zbtlink,zbt-we5927; }
timeout() {
  [ "$*" = '3 swconfig dev switch0 show' ] || return 1
  printf '%s\\n' 'link: port:0 link:down' 'link: port:3 link:up speed:100baseT full-duplex' 'link: port:4 link:up' 'link: port:6 link:up speed:1000baseT'
}
main call ethernetPorts
"""
        result = ash(without_main(STATUS) + stub)
        result.check_returncode()
        data = json.loads(result.stdout)
        self.assertTrue(data["available"])
        self.assertEqual([p["port"] for p in data["ports"]], list(range(5)))
        self.assertEqual([p["link"] for p in data["ports"]],
                         ["down", "unknown", "unknown", "up", "up"])

    def test_ethernet_unavailable_for_wrong_board_or_switch_error(self):
        for board, operation in [("other", "echo unexpected >&2"), ("zbtlink,zbt-we5927", "return 1"),
                                 ("zbtlink,zbt-we5927", "echo 'link: port:6 link:up'")]:
            with self.subTest(board=board, operation=operation):
                stub = f"live_board() {{ echo {board}; }}\ntimeout() {{ {operation}; }}\nmain call ethernetPorts"
                result = ash(without_main(STATUS) + stub)
                result.check_returncode()
                self.assertEqual(json.loads(result.stdout), {"available": False, "ports": []})
                self.assertEqual(result.stderr, "")

    def test_status_never_runs_mutating_network_commands(self):
        code = "\n".join(x for x in STATUS.splitlines()
                         if not x.lstrip().startswith("#"))
        for unsafe in (r"\bwifi\s+(?:reload|up|down)\b",
                       r"\bif(?:up|down)\b", r"\b(?:reboot|sysupgrade|kill)\b",
                       r"\bAT\+CFUN", r"\bmodprobe\b", r"\buci\s+(?:set|commit)"):
            self.assertNotRegex(code, unsafe)
        self.assertIn('call "hostapd.$interface" get_status', STATUS)
        self.assertIn('internet_verified":null', STATUS)

    def test_package_rejects_core_luci_and_kernel_mutations(self):
        code = (without_main(PKGS) + """
for name in kernel kmod-mt7603 base-files procd netifd uhttpd luci-app-firewall apk-tools ../x --no-signature ; do
  if package_valid "$name"; then echo "BAD:$name"; else echo "BLOCKED:$name"; fi
done
for name in sqm-scripts wireguard-tools ddns-scripts veci-app-guest; do
  if package_valid "$name"; then echo "ALLOWED:$name"; else echo "BAD:$name"; fi
done
""")
        result = ash(code)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("BAD:", result.stdout)
        self.assertEqual(result.stdout.count("BLOCKED:"), 10)
        self.assertEqual(result.stdout.count("ALLOWED:"), 4)

    def test_install_needs_explicit_confirmation_before_apk(self):
        p = ash(without_main(PKGS) + """
apk() { echo UNSAFE_EXECUTED >&2; return 0; }
install sqm-scripts no
""")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("confirmation_required", p.stdout)
        self.assertNotIn("UNSAFE_EXECUTED", p.stderr)

    def test_signed_repository_allowlist_and_resource_guards(self):
        self.assertIn("https://downloads.openwrt.org/releases/25.12.6/", PKGS)
        self.assertIn("app_feed_verified_build_id", PKGS)
        self.assertIn("4096", PKGS)
        self.assertIn("16384", PKGS)
        self.assertIn("apk --simulate add", PKGS)
        self.assertNotIn("--allow-untrusted", PKGS)
        self.assertIn("kmod-", PKGS)
        self.assertIn("automatic_install", PKGS)

    def test_single_source_package_ownership_no_duplicate_backend(self):
        self.assertFalse((BASE / "backend").exists())
        for module, executable, acl in (
            ("veci-v2-runtime", "veci2-status", "veci2-status-acl.json"),
            ("veci-v2-package-manager", "veci2-apk", "veci2-apk-acl.json"),
        ):
            pkg = BASE / "packages" / module
            self.assertTrue((pkg/executable).exists())
            self.assertTrue((pkg/acl).exists())
            manifest = (pkg/"Makefile").read_text()
            self.assertIn("$(INSTALL_BIN)", manifest)
            self.assertIn("$(INSTALL_DATA)", manifest)
            self.assertIn("rpcd", manifest)

    def test_sms_contract_uses_existing_serialized_transport_not_double_AT(self):
        self.assertIn('"sms_center_contract":"veci.sms"', STATUS)
        self.assertIn('list veci.sms', STATUS)
        self.assertNotIn("we5927-at", STATUS)
        self.assertNotIn("AT+CMGS", STATUS)
        acl = json.loads((BASE/"packages/veci-v2-runtime/veci2-status-acl.json").read_text())
        self.assertEqual(acl["veci-v2-runtime"]["write"], {"ubus": {}})
        sms_acl = (ROOT/"source/veci-cellular-we5927/files/usr/share/rpcd/acl.d/"
                   "veci-cellular-we5927.json")
        self.assertIn("sendMessage", sms_acl.read_text())

if __name__ == "__main__":
    unittest.main()
