"""Offline tests for corrected minified VeCI UI overlay, no router access."""
import hashlib
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/veci-sms-storage-ui-built-hotfix-v11.sh"
PAYLOAD = ROOT / "scripts/veci-sms-storage-ui-built-v1"

class UiTerserV11(unittest.TestCase):
    def test_posix_sh_syntax(self):
        r = subprocess.run(["sh", "-n", str(SCRIPT)], text=True, capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_pinned_minified_payload_exact_sha(self):
        s = SCRIPT.read_text()
        m = {"OLD_SHA": "expected-cellular.js",
             "NEW_SHA": "new-cellular.js",
             "HELPER_SHA": "new-messaging.js"}
        for variable, filename in m.items():
            with self.subTest(file=filename):
                match = re.search(rf"(?m)^{variable}=([0-9a-f]{{64}})$", s)
                self.assertIsNotNone(match)
                actual = hashlib.sha256((PAYLOAD / filename).read_bytes()).hexdigest()
                self.assertEqual(actual, match.group(1))
        self.assertIn("SOURCE_SHA=15f8a6afd4e16ff8f58bcfe5545f045fc3f943cf", s)

    def test_correctly_checks_compiled_not_unminified_asset(self):
        s = SCRIPT.read_text()
        self.assertIn("expected-cellular.js", s)
        self.assertIn("new-cellular.js", s)
        self.assertIn("new-messaging.js", s)
        self.assertIn("installed_asset_not_verified_untouched", s)
        self.assertIn("CURRENT_CELLULAR_SHA=", s)
        self.assertIn("CURRENT_CELLULAR_BYTES=", s)
        self.assertIn("cmp -s \"$PAGE\" \"$work/old\"", s)
        old = (PAYLOAD / "expected-cellular.js").read_text()
        new = (PAYLOAD / "new-cellular.js").read_text()
        self.assertIn("import{", old)
        self.assertIn("smsStorageLabel", new)
        self.assertNotIn("\nfunction normalizeOperator(", old)
        self.assertNotEqual(old, new)

    def test_no_modem_command_or_daemon_restart(self):
        s = SCRIPT.read_text()
        self.assertIn("NO_AT_COMMAND_SENT_BY_INSTALLER", s)
        for disallowed in ("we5927-at /dev", "/etc/init.d/rpcd restart",
                           "AT+CMGL=4' 5000", "AT+CUSD=1' 1500", 
                           "sysupgrade -", "uci set ", "reboot "):
            self.assertNotIn(disallowed, s)
        self.assertIn("PAGE=/www/veci/js/pages/cellular.js", s)
        self.assertIn("HELPER=/www/veci/js/lib/messaging.js", s)

    def test_backups_are_isolated_and_atomic(self):
        s = SCRIPT.read_text()
        self.assertIn("BACKUP=/root/veci-sms-storage-ui-v11-rollback", s)
        self.assertIn("original-page", s)
        self.assertIn("backup_ok", s)
        self.assertIn("atomic_write", s)
        self.assertIn("trap cleanup EXIT", s)
        self.assertIn("UI_V11_ROLLBACK_PASS", s)
        self.assertIn("UI_V11_LIVE_ASSETS_PASS", s)
        self.assertIn("[ ! -e \"$BACKUP\" ]", s)
        self.assertNotIn("veci-storage-hotfix-rollback", s)
        self.assertNotIn("veci-capability-hotfix-rollback", s)

    def test_only_known_safe_metadata_is_exposed(self):
        src = (PAYLOAD / "new-cellular.js").read_text()
        fmt = (PAYLOAD / "new-messaging.js").read_text()
        self.assertIn("messagingStorage", src)
        self.assertIn("Check stored SMS count", src)
        self.assertIn("SMS Inbox is not enabled yet", src)
        self.assertIn("Number.isSafeInteger", fmt)
        self.assertIn("read_only_at_cpms", fmt)
        self.assertNotIn("AT+CMGL=4", src)
        self.assertNotIn("AT+CUSD=1", src)

if __name__ == "__main__":
    unittest.main()
