"""Exercise the actual OEM shell adapter and gateway using isolated command fixtures."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "rebuild/oem-updated/backend"

JSHN = """
json_init() { :; }
json_add_string() { printf 'string:%s=%s\n' "$1" "$2"; }
json_add_array() { printf 'array:%s\n' "$1"; }
json_add_object() { :; }
json_close_array() { :; }
json_close_object() { :; }
json_dump() { :; }
""".replace("\\\n", "\n")

class ModuleStatus(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture = self.root / "jshn.sh"
        self.fixture.write_text(JSHN)
        self.env = dict(os.environ, PATH=str(self.root)+":"+os.environ["PATH"],
                        HTTPS="on", REQUEST_METHOD="GET", HTTP_X_OEM_SESSION="a"*32)
        self.command("uci", 'printf "%s\n" "${DEVICE:-usb0}"')
        self.command("ubus", 'printf "%s\n" "{}"')
        self.command("jsonfilter", r"""
case "$2" in
  '@.up') echo "${LINK_UP:-true}";;
  '@.uptime') echo 23;;
  *ipv4-address*) echo 192.168.7.2;;
  *ipv6-address*) echo 2001:db8::2;;
  '@.access') echo "${PERMIT:-true}";;
  *) exit 1;;
esac
""")
        self.command("cat", r"""
case "$1" in
 */address) echo 00:11:22:33:44:55;;
 */rx_bytes) echo "${RX:-12345678901}";;
 */tx_bytes) echo 987;;
 *) exit 1;;
esac
""")
        adapter = (ROOT/"read-only-adapter.sh").read_text().replace(
            "/usr/share/libubox/jshn.sh", str(self.fixture))
        (self.root/"adapter").write_text(adapter)
        self.command("gateway-adapter", 'printf "ADAPTER_CALLED:%s\n" "$1"')
        gateway = (ROOT/"webapi").read_text().replace(
            "/usr/share/libubox/jshn.sh", str(self.fixture)).replace(
            "/usr/libexec/oem-updated/read-only-adapter", str(self.root/"gateway-adapter"))
        (self.root/"gateway").write_text(gateway)

    def command(self, name, script):
        p = self.root/name
        p.write_text("#!/bin/sh\n"+script+"\n")
        p.chmod(0o755)

    def run_script(self, name, *args, **env):
        return subprocess.run(["sh", str(self.root/name), *args],
                              env=dict(self.env, **env), text=True,
                              capture_output=True, timeout=5)

    def test_modem_status_uses_live_counter_and_link_state(self):
        r = self.run_script("adapter", "get_module_status")
        self.assertEqual(r.returncode, 0, r.stderr)
        for x in ("string:host=192.168.7.2", "string:rxall=12345678901",
                  "string:txall=987", "string:uptime=23", "string:=2001:db8::2"):
            self.assertIn(x, r.stdout)

    def test_5ghz_board_policy_refuses_all_vendor_forms(self):
        for op in ("getWiFi5", "setWiFi5", "setWiFi5_nocommit", "get_wifi_guest5", "set_wifi_guest5"):
            for method in ("GET", "POST"):
                with self.subTest(operation=op, method=method):
                    result = self.run_script("gateway", QUERY_STRING="op="+op, REQUEST_METHOD=method)
                    self.assertIn("5 GHz radio unavailable", result.stdout)
                    self.assertNotIn("ADAPTER_CALLED", result.stdout)
                    denied = self.run_script("gateway", QUERY_STRING="op="+op, PERMIT="false", REQUEST_METHOD=method)
                    self.assertIn("access denied", denied.stdout)

    def test_down_link_does_not_return_stale_ip(self):
        r = self.run_script("adapter", "get_module_status", LINK_UP="false")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("string:host=0.0.0.0", r.stdout)
        self.assertIn("string:uptime=0", r.stdout)
        self.assertNotIn("2001:db8", r.stdout)

    def test_bad_device_counter_or_state_fails_closed(self):
        for env in (dict(DEVICE="eth0"), dict(RX="bad"), dict(LINK_UP="unknown")):
            r = self.run_script("adapter", "get_module_status", **env)
            self.assertNotEqual(r.returncode, 0)
            self.assertNotIn("string:code=1", r.stdout)

    def test_gateway_accepts_only_single_modem_and_authenticated_get(self):
        for suffix in ("", "&module_section=4gwan", "&module_section=lte"):
            r = self.run_script("gateway", QUERY_STRING="op=get_module_status"+suffix)
            self.assertIn("ADAPTER_CALLED:get_module_status", r.stdout)
        for query, env in (
            ("op=get_module_status&module_section=eth0", {}),
            ("op=get_module_status&module_section=lte&module_section=lte", {}),
            ("op=get_lan_config&module_section=lte", {}),
            ("op=get_module_status", dict(PERMIT="false")),
            ("op=get_module_status", dict(REQUEST_METHOD="POST")),
            ("op=get_module_status", dict(HTTPS="off")),
            ("op=get_module_status", dict(HTTP_X_OEM_SESSION="")),
        ):
            r = self.run_script("gateway", QUERY_STRING=query, **env)
            self.assertNotIn("ADAPTER_CALLED", r.stdout)

    def test_network_read_dispatch_and_duplicate_empty_op(self):
        for op in ("get_module_signal","get_arp","get_dhcp_allocation","get_wan_config"):
            r = self.run_script("gateway", QUERY_STRING="op="+op)
            self.assertIn("ADAPTER_CALLED:"+op,r.stdout)
            r = self.run_script("gateway", QUERY_STRING="op="+op, PERMIT="false")
            self.assertNotIn("ADAPTER_CALLED",r.stdout)
            r = self.run_script("gateway", QUERY_STRING="op=&op="+op)
            self.assertNotIn("ADAPTER_CALLED",r.stdout)
        r = self.run_script("gateway", QUERY_STRING="op=get_module_signal&module_section=4gwan")
        self.assertIn("ADAPTER_CALLED:get_module_signal",r.stdout)
