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

    def test_privileged_modem_controls_are_disabled(self):
        for op, message in (("send_at", "Raw modem commands disabled"),
                            ("set_imei", "Modem identity is read-only")):
            for method in ("GET", "POST"):
                with self.subTest(op=op, method=method):
                    args = dict(QUERY_STRING="op="+op, REQUEST_METHOD=method)
                    allowed_session = self.run_script("gateway", **args)
                    self.assertIn(message, allowed_session.stdout)
                    self.assertNotIn("ADAPTER_CALLED", allowed_session.stdout)
                    denied = self.run_script("gateway", HTTP_X_OEM_SESSION="", **args)
                    self.assertIn("access denied", denied.stdout)
        identity = self.run_script("gateway", QUERY_STRING="op=get_imei")
        self.assertIn("ADAPTER_CALLED:get_imei", identity.stdout)

    def test_gps_and_voice_require_session_and_refuse_hardware_calls(self):
        for op in ("get_gps", "get_voice", "set_voice"):
            for method in ("GET", "POST"):
                with self.subTest(op=op, method=method):
                    args = dict(QUERY_STRING="op="+op, REQUEST_METHOD=method)
                    result = self.run_script("gateway", **args)
                    self.assertIn("Service not supported", result.stdout)
                    self.assertNotIn("ADAPTER_CALLED", result.stdout)
                    denied = self.run_script("gateway", PERMIT="false", **args)
                    self.assertIn("access denied", denied.stdout)

    def test_legacy_tunnel_mesh_and_arbitrary_url_upgrade_refused(self):
        for op in ("config_ss_redir","config_ss_tunnel_dns","config_ss_tunnel_server","mesh_botton","url_upgrade"):
            for method in ("GET","POST"):
                with self.subTest(op=op,method=method):
                    args=dict(QUERY_STRING="op="+op,REQUEST_METHOD=method)
                    result=self.run_script("gateway",**args)
                    self.assertIn("not supported",result.stdout)
                    self.assertNotIn("ADAPTER_CALLED",result.stdout)
                    denied=self.run_script("gateway",HTTP_X_OEM_SESSION="",**args)
                    self.assertIn("access denied",denied.stdout)

    def test_legacy_topology_storage_mptcp_write_refused(self):
        for op in ("set_port","set_disk","enable_mptcp_set"):
            for method in ("GET","POST"):
                with self.subTest(op=op,method=method):
                    args=dict(QUERY_STRING="op="+op,REQUEST_METHOD=method)
                    result=self.run_script("gateway",**args)
                    self.assertIn("not supported",result.stdout)
                    self.assertNotIn("ADAPTER_CALLED",result.stdout)
                    denied=self.run_script("gateway",HTTP_X_OEM_SESSION="",**args)
                    self.assertIn("access denied",denied.stdout)

    def test_legacy_wizard_staging_refused(self):
        for op in ("set_wan_config_nocommit","setWiFi2_nocommit","guide_commit"):
            for method in ("GET","POST"):
                with self.subTest(op=op,method=method):
                    args=dict(QUERY_STRING="op="+op,REQUEST_METHOD=method)
                    result=self.run_script("gateway",**args)
                    self.assertIn("Legacy wizard staging is not supported",result.stdout)
                    self.assertNotIn("ADAPTER_CALLED",result.stdout)
                    denied=self.run_script("gateway",HTTP_X_OEM_SESSION="",**args)
                    self.assertIn("access denied",denied.stdout)

    def test_legacy_cloud_and_bootflag_refused(self):
        for op in ("activate_ngrokc","get_cloud_login","set_cloud_login","get_ac_info","set_ac_info","get_ac_switch","set_ac_switch","bootflag","setbootflag"):
            for method in ("GET","POST"):
                with self.subTest(op=op,method=method):
                    args=dict(QUERY_STRING="op="+op,REQUEST_METHOD=method)
                    result=self.run_script("gateway",**args)
                    self.assertIn("not supported",result.stdout)
                    self.assertNotIn("ADAPTER_CALLED",result.stdout)
                    denied=self.run_script("gateway",HTTP_X_OEM_SESSION="",**args)
                    self.assertIn("access denied",denied.stdout)

    def test_ddns_events_hide_credentials_and_unrelated_messages(self):
        self.command("jsonfilter", """case "$2" in
          '@.ok') echo true;;
          '@.logs') printf '%s\n' 'Thu Nov 26 12:00:01 2026 user.err ddns-scripts[2]: failed url?secret=sensitive' 'Thu Nov 26 12:00:02 2026 user.info other: ddns start';;
          *) exit 1;;
        esac""")
        result = self.run_script("adapter", "get_ddns_log")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("string:ddns_log=DDNS error", result.stdout)
        self.assertNotIn("sensitive", result.stdout)
        self.assertNotIn("DDNS start", result.stdout)

    def test_ddns_log_requires_native_log_scope(self):
        self.command("ubus", """case "$*" in *veci.v2.system*) echo false;; *) echo true;; esac""")
        self.command("jsonfilter", "cat")
        self.command("cat", "/bin/cat")
        for op in ("get_ddns_log", "get_log_list", "get_4g_log"):
            with self.subTest(op=op):
                result = self.run_script("gateway", QUERY_STRING="op="+op)
                self.assertIn("native log permission denied", result.stdout)
                self.assertNotIn("ADAPTER_CALLED", result.stdout)

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
