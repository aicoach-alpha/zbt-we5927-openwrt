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
        script = setup + "\n" + func(self.source, name) + "\n" + invocation + "\n"
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
        self.assertIn("hostapd.phy0-ap0", body)
        self.assertNotIn("iw dev", body)

    def test_checks_services_up(self):
        mocks = """
ubus() { :; }
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
ubus() { :; }
jsonfilter() {
 case "$2" in
   '@.radio0.up') echo true ;;
   '@.status') echo DISABLED ;;
 esac
}
"""
        self.assertEqual(self.shell(mocks, "radio_running", "radio_running; echo rc=$?"), "rc=1")

    def test_rx_pse_is_read_only(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "reset"
            path.write_text("TX hang: 0\nRX PSE busy stuck: 2\nMCU hang: 0\n")
            script = "RESET=" + str(path).replace("\\", "/") + "\n"
            self.assertEqual(self.shell(script, "rx_pse_resets", "rx_pse_resets"), "2")

    def test_state_cannot_claim_beacon_verified(self):
        self.assertIn("beacon_verified=0", func(self.source, "write_state"))
        self.assertIn("auto_recover=0", func(self.source, "write_state"))
        self.assertIn("manual_recovery_required", func(self.source, "daemon"))
        self.assertNotIn("wifi up", func(self.source, "daemon"))

if __name__ == "__main__":
    unittest.main()
