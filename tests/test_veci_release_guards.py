#!/usr/bin/env python3
"""Non-live safety regression checks for the VeCI WE5927 release candidate.

Run on CI; never connects to or changes a physical router.
"""
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "source" / "veci.commit"
GUEST = ROOT / "source/veci-app-guest/files/usr/libexec/rpcd/veci.app.guest"
VOUCHER = ROOT / "source/veci-app-voucher/files/usr/libexec/rpcd/veci.app.voucher"
UPDATE_AGENT = ROOT / "source/veci-update-we5927/files/usr/sbin/veci-update-agent"
UPDATER_PROFILE = ROOT / "source/veci-update-we5927/files/etc/uci-defaults/96-veci-update-we5927"
SCRIPT_PATHS = [GUEST, VOUCHER, UPDATE_AGENT, UPDATER_PROFILE]


class ReleaseSafetyTests(unittest.TestCase):
    def test_firmware_is_pinned_to_immutable_commit(self):
        self.assertRegex(CORE.read_text().strip(), r"^[0-9a-f]{40}$")

    def test_shell_providers_parse(self):
        for script in SCRIPT_PATHS:
            with self.subTest(script=script.name):
                p = subprocess.run(["sh", "-n", str(script)], capture_output=True, text=True)
                self.assertEqual(p.returncode, 0, p.stderr)

    def test_guest_has_single_lifecycle_and_stays_closed_until_ready(self):
        text = GUEST.read_text()
        for name in ("enable_portal", "disable_portal", "method_action", "method_cleanup"):
            with self.subTest(name=name):
                self.assertEqual(len(re.findall(rf"(?m)^{name}\(\) \{{", text)), 1)
        self.assertIn("set wireless.veci_guest.disabled='1'", text)
        self.assertIn("uci set wireless.veci_guest.disabled='0'", text)
        self.assertIn("service_restart uspot || return 1", text)
        first_up = text.index("service_restart uspot || return 1")
        first_radio = text.index("uci set wireless.veci_guest.disabled='0'")
        self.assertLess(first_up, first_radio, "radio must not open before the captive service")

    def test_voucher_expiry_and_revoke_disconnect_clients(self):
        text = VOUCHER.read_text()
        self.assertIn("disconnect_voucher_clients", text)
        self.assertGreaterEqual(text.count('disconnect_voucher_clients "$code"'), 2)
        self.assertIn("cleanupExpired) method_cleanup", text)
        self.assertIn("cleanup) method_cleanup_all", text)
        cleaner = (ROOT / "source/veci-app-voucher/files/usr/sbin/veci-voucher-cleaner").read_text()
        self.assertIn("cleanupExpired", cleaner)

    def test_auto_firmware_install_is_opt_in_with_signature_gate(self):
        text = UPDATE_AGENT.read_text()
        self.assertIn('veci.update.auto_install', text)
        self.assertIn('[ "$signature_verified" = "true" ]', text)
        self.assertIn('apply_token', text)
        self.assertIn('veci.update.auto_keep_settings', text)
        self.assertNotIn("sysupgrade -F", text)
        profile = UPDATER_PROFILE.read_text()
        self.assertIn("veci.update.auto_install='0'", profile)
        self.assertIn("veci.update.auto_download='0'", profile)

    def test_release_channel_requires_signed_metadata(self):
        publish = (ROOT / ".github/workflows/publish-veci-release.yml").read_text()
        for token in (
            "VECI_FIRMWARE_SIGNING_KEY_B64",
            "VECI_FIRMWARE_SIGNING_PUB_B64",
            "ucert -V",
            'CHANNEL_FILE=\'channel-prerelease.json\'',
            'CHANNEL_FILE=\'channel-stable.json\'',
        ):
            self.assertIn(token, publish)

    def test_app_packages_built_as_modules(self):
        wf = (ROOT / ".github/workflows/j8c-app-feed.yml").read_text()
        for name in ("guest", "sqm", "ddns", "wireguard", "voucher"):
            self.assertIn(f"set_module PACKAGE_veci-app-{name}", wf)
            self.assertIn(f"require_config PACKAGE_veci-app-{name} m", wf)


if __name__ == "__main__":
    unittest.main(verbosity=2)
