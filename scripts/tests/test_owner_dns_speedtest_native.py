"""Source/host checks for VeCI DNS and browser-side LTE speed-test."""
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
B = ROOT / "rebuild/veci-v2/packages"
DNS = (B / "veci-v2-runtime/veci2-dns").read_text()
UI = (B / "veci-v2-ui/files/www/veci2/index.html").read_text()
JS = (B / "veci-v2-ui/files/www/veci2/dns-settings.js").read_text()
SPEED = (B / "veci-v2-ui/files/www/veci2/speed-test.js").read_text()


class NativeDnsSpeedTest(unittest.TestCase):
    def test_dns_ip_strict_ipv4_table(self):
        funcs = DNS.split('[ "$#" -ge 1 ] || fail unsupported_method')[0]
        cases = {
            "1.1.1.1": True, "8.8.8.8": True, "9.9.9.9": True,
            "149.112.112.112": True, "94.140.14.14": True,
            "0.0.0.0": False, "127.0.0.1": False, "224.0.0.1": False,
            "256.1.1.1": False, "1.1.1": False, "1.1.1.1.1": False,
            "1.1.1.": False, "1..1.1": False, "01.1.1.1": False,
            "1.1.1.1;touch /tmp/pwn": False, "": False,
        }
        for ip, expected in cases.items():
            with self.subTest(ip=ip):
                proc = subprocess.run(
                    ["sh", "-c", funcs + 'valid_ipv4 "$1"', "_", ip],
                    capture_output=True, text=True, timeout=5)
                self.assertEqual(proc.returncode == 0, expected, proc.stderr)

    def test_dns_provider_acl_and_rollback(self):
        acl = json.loads((B / "veci-v2-runtime/veci2-status-acl.json").read_text())
        self.assertEqual(acl["veci-v2-dns"]["read"]["ubus"]["veci.v2.dns"], ["status"])
        self.assertEqual(acl["veci-v2-dns"]["write"]["ubus"]["veci.v2.dns"], ["set"])
        for required in ("zbtlink,zbt-we5927", "pending_dhcp_changes",
                         "flock -n 9", 'cp "$tmp/original" /etc/config/dhcp',
                         "/etc/init.d/dnsmasq restart", 'uci -q -t "$tmp" commit dhcp'):
            self.assertIn(required, DNS)
        for forbidden in ("ifdown", "ifup", "wifi reload", "AT+CFUN"):
            self.assertNotIn(forbidden, DNS)
        self.assertIn("veci2-dns $(1)/usr/libexec/rpcd/veci.v2.dns",
                      (B / "veci-v2-runtime/Makefile").read_text())

    def test_speedtest_bounded_browser_only(self):
        for required in ("https://speed.cloudflare.com", "credentials: 'omit'",
                         "new AbortController()", "1048576", "524288"):
            self.assertIn(required, SPEED)
        self.assertNotIn("/cgi-bin/", SPEED)
        self.assertIn("https://speed.cloudflare.com;", UI)
        self.assertIn("Speed Test Lite", UI)
        self.assertIn('id="speedtest-cancel"', UI)

    def test_dns_ui_and_existing_navigation(self):
        self.assertEqual(UI.count('class="tab"'), 3)
        self.assertEqual(UI.count('class="tab active"'), 1)
        self.assertIn("DNS Settings", UI)
        self.assertIn("dns-settings.js", UI)
        self.assertIn("window.confirm", JS)
        self.assertIn("veci.v2.dns", JS)
        mk = (B / "veci-v2-ui/Makefile").read_text()
        for name in ("speed-test.js", "dns-settings.js"):
            self.assertIn(name, mk)

    def test_javascript_and_shell_syntax(self):
        for cmd in [
            ["node", "--check", str(B / "veci-v2-ui/files/www/veci2/speed-test.js")],
            ["node", "--check", str(B / "veci-v2-ui/files/www/veci2/dns-settings.js")],
            ["node", "--check", str(B / "veci-v2-ui/files/www/veci2/app.js")],
            ["sh", "-n", str(B / "veci-v2-runtime/veci2-dns")],
        ]:
            with self.subTest(command=cmd):
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
