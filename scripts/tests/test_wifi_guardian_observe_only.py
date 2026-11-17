"""Offline regression checks for MT7628 Wi-Fi Guardian: never reload a hung driver."""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "source/veci-wifi-guardian/veci-wifi-guardian"
SH = shutil.which("sh") or r"C:\Program Files\Git\usr\bin\sh.exe"

def func(source, name):
    found = re.search(rf"(?ms)^{name}\(\) \{{\n.*?^\}}\n", source)
    if not found:
        raise AssertionError("Missing function: " + name)
    return found.group(0)

class GuardianSafety(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")

    def shell(self, setup, name, invocation, env=None):
        # PowerShell-launched Git Bash lacks /usr/bin in inherited PATH.
        script = "PATH=/usr/bin:/bin:$PATH\n" + setup + "\n" + func(self.source, name) + "\n" + invocation + "\n"
        result = subprocess.run([str(SH), "-c", script], text=True, capture_output=True,
                                timeout=6, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_never_mutates_radio_or_modem(self):
        lines = [line for line in self.source.splitlines()
                 if not line.lstrip().startswith("#")]
        code = "\n".join(lines)
        for pattern in [r"\bwifi\s+(?:up|down|reload)\b", r"\bifdown\b", r"\bifup\b",
                        r"\breboot\b", r"\bpower_cycle\b"]:
            self.assertNotRegex(code, pattern)

    def test_runtime_status_uses_bounded_ubus_not_iw(self):
        body = func(self.source, "radio_running")
        self.assertIn("ubus -S -t 3", body)
        self.assertIn("hostapd.*", body)
        self.assertIn("wifi_netdev_present", body)
        self.assertNotIn("iw dev", body)

    def test_checks_services_up(self):
        mocks = """
wifi_netdev_present() { return 0; }
ubus() {
 if [ "$4" = list ]; then echo hostapd.phy0-ap0; else echo '{}'; fi
}
jsonfilter() {
 case "$2" in
   '@.radio0.up') echo true ;;
   '@.status') echo ENABLED ;;
 esac
}
"""
        self.assertEqual(self.shell(mocks, "radio_running", "radio_running; echo rc=$?"), "rc=0")

    def test_detects_disabled_hostapd(self):
        mocks = """
wifi_netdev_present() { return 0; }
ubus() {
 if [ "$4" = list ]; then echo hostapd.phy0-ap0; else echo '{}'; fi
}
jsonfilter() {
 case "$2" in
   '@.radio0.up') echo true ;;
   '@.status') echo DISABLED ;;
 esac
}
"""
        self.assertEqual(self.shell(mocks, "radio_running", "radio_running; echo rc=$?"), "rc=1")

    def test_rejects_missing_wifi_netdev_even_when_radio_is_up(self):
        mocks = """
wifi_netdev_present() { return 1; }
ubus() { if [ "$4" = list ]; then echo hostapd.phy0-ap0; else echo '{}'; fi; }
jsonfilter() { case "$2" in '@.radio0.up') echo true;; '@.status') echo ENABLED;; esac; }
"""
        self.assertEqual(self.shell(mocks, "radio_running", "radio_running; echo rc=$?"), "rc=1")

    def test_accepts_actual_hostapd_object_without_hardcoded_ifname(self):
        mocks = """
wifi_netdev_present() { return 0; }
ubus() { if [ "$4" = list ]; then echo hostapd.wlan0; else echo '{}'; fi; }
jsonfilter() { case "$2" in '@.radio0.up') echo true;; '@.status') echo ENABLED;; esac; }
"""
        self.assertEqual(self.shell(mocks, "radio_running", "radio_running; echo rc=$?"), "rc=0")

    def test_rejects_missing_hostapd_object(self):
        mocks = """
wifi_netdev_present() { return 0; }
ubus() { echo '{}'; }
jsonfilter() { case "$2" in '@.radio0.up') echo true;; '@.status') echo ENABLED;; esac; }
"""
        self.assertEqual(self.shell(mocks, "radio_running", "radio_running; echo rc=$?"), "rc=1")

    def test_failure_reason_distinguishes_missing_interface(self):
        mocks = """
phy_available() { return 0; }
wifi_netdev_present() { return 1; }
ubus() { echo '{}'; }
jsonfilter() { echo true; }
"""
        self.assertEqual(self.shell(mocks, "ap_failure_reason", "ap_failure_reason"),
                         "wifi_netdev_missing")

    def test_persistent_failure_status_and_alert_suppression(self):
        daemon = func(self.source, "daemon")
        self.assertIn("last_alert", daemon)
        self.assertIn('failures="$threshold"', daemon)
        self.assertIn("manual_recovery_required", daemon)
        self.assertIn('reason=$reason', daemon)
        state = func(self.source, "write_state")
        self.assertIn("reason=%s", state)
        self.assertIn("beacon_verified=0", state)

    def test_rx_pse_is_read_only(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "reset"
            path.write_text("TX hang: 0\nRX PSE busy stuck: 2\nMCU hang: 0\n")
            native = str(path).replace("\\", "/")
            if os.name == "nt" and re.match(r"^[A-Za-z]:/", native):
                native = "/" + native[0].lower() + native[2:]
            script = "RESET=" + native + "\n"
            self.assertEqual(self.shell(script, "rx_pse_resets", "rx_pse_resets"), "2")

    def test_state_cannot_claim_beacon_verified(self):
        self.assertIn("beacon_verified=0", func(self.source, "write_state"))
        self.assertIn("auto_recover=0", func(self.source, "write_state"))
        self.assertIn("manual_recovery_required", func(self.source, "daemon"))
        self.assertNotIn("wifi up", func(self.source, "daemon"))

    def test_first_fault_capture_classifies_events_and_redacts_sensitive_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "first-fault.txt"
            setup = f"""
FIRST_FAULT='{path.as_posix()}'
TAG=veci-wifi-guardian
wifi_netdev_present() {{ return 1; }}
ubus() {{ return 0; }}
logger() {{ :; }}
logread() {{
  printf '%s\\n' 'Mon Nov 16 12:05:43 router daemon.err hostapd: Failed to setup interface secretSSID wifi_password=SENSITIVE' \\
    'Mon Nov 16 12:05:44 router daemon.notice veci-rpc-net: wifi_reload_requested' \\
    'Mon Nov 16 12:05:45 router daemon.notice netifd: Wireless device radio0 is down'
}}
dmesg() {{
  printf '%s\\n' '[ 1028.057864] br-lan: port 2(phy0-ap0) entered disabled state' \\
    '[ 1139.397913] mt76_wmac 10300000.wmac phy0-ap0 (unregistering): left allmulticast mode'
}}
"""
            output = self.shell(setup, "capture_first_fault",
                                "capture_first_fault wifi_netdev_missing lost_after_ready; echo rc=$?")
            self.assertEqual(output, "rc=0")
            data = path.read_text()
            self.assertIn("schema=veci_wifi_first_fault_v1", data)
            self.assertIn("reason=wifi_netdev_missing", data)
            self.assertIn("first_observed_stage=lost_after_ready", data)
            self.assertIn("class=hostapd_error", data)
            self.assertIn("class=veci_wifi_reload_requested", data)
            self.assertIn("class=netifd_wifi_event", data)
            self.assertIn("class=bridge_wifi_disabled", data)
            self.assertIn("class=mt76_wifi_unregistering", data)
            self.assertIn("kernel_uptime_s=1028.057864", data)
            self.assertNotIn("secretSSID", data)
            self.assertNotIn("SENSITIVE", data)
            if os.name != "nt":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_first_fault_is_captured_only_once(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "first-fault.txt"
            setup = f"""
FIRST_FAULT='{path.as_posix()}'
TAG=veci-wifi-guardian
wifi_netdev_present() {{ return 1; }}
ubus() {{ :; }}
logger() {{ :; }}
logread() {{ :; }}
dmesg() {{ :; }}
"""
            self.shell(setup, "capture_first_fault",
                       "capture_first_fault wifi_netdev_missing lost_after_ready; "
                       "capture_first_fault phy_missing startup_unavailable; echo rc=$?")
            data = path.read_text()
            self.assertIn("reason=wifi_netdev_missing", data)
            self.assertNotIn("reason=phy_missing", data)
            self.assertFalse((Path(directory) / "first-fault.txt.tmp").exists())

    def test_first_fault_does_not_mutate_router_and_delays_startup_capture(self):
        body = func(self.source, "capture_first_fault")
        for regex in (r"\\bwifi\\s+(?:up|down|reload)\\b",
                      r"\\b(?:ifup|ifdown|reboot|sysupgrade|modprobe|rmmod)\\b",
                      r"\\buci\\s+(?:set|commit|delete)\\b"):
            self.assertNotRegex(body, regex)
        self.assertIn("logread", body)
        self.assertIn("dmesg", body)
        self.assertIn("tail -n 320", body)
        daemon = func(self.source, "daemon")
        self.assertIn("ever_ready=1", daemon)
        self.assertIn('capture_first_fault "$reason" lost_after_ready', daemon)
        self.assertIn('"$boot_age" -lt 240', daemon)
        self.assertIn("startup_unavailable", daemon)
        self.assertIn("evidence) if [ -r", self.source)

if __name__ == "__main__":
    unittest.main()
