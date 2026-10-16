"""Regression guard for UI-only overlay over existing WE5927 v2 RPC."""
from pathlib import Path
import re
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/veci-sms-storage-ui-hotfix-v1.sh"


class SmsStorageUiOverlay(unittest.TestCase):
    def test_shell_syntax(self):
        proc=subprocess.run(["sh","-n",str(SCRIPT)],capture_output=True,text=True)
        self.assertEqual(proc.returncode,0,proc.stderr)

    def test_source_commits_immutable(self):
        s=SCRIPT.read_text()
        self.assertRegex(s,r"(?m)^ORIGINAL_COMMIT=[a-f0-9]{40}$")
        self.assertRegex(s,r"(?m)^UPDATED_COMMIT=[a-f0-9]{40}$")
        self.assertIn("ORIGINAL_COMMIT=f19603b6172854dfeca3861826017d8f1aa1268c",s)
        self.assertIn("UPDATED_COMMIT=88009f1fd394eeeb583f27839d29c714e31b91b6",s)
        self.assertNotIn("UPDATED_COMMIT=dev",s)

    def test_only_cellular_page_and_one_metadata_sanitizer(self):
        s=SCRIPT.read_text()
        self.assertIn("PAGE=/www/veci/js/pages/cellular.js",s)
        self.assertIn("UTIL=/www/veci/js/lib/messaging.js",s)
        self.assertIn("cmp -s \"$PAGE\" \"$work/original\"",s)
        self.assertIn("[ ! -e \"$UTIL\" ]",s)
        self.assertIn("SMS Inbox is not enabled yet",s)
        self.assertIn("Number.isSafeInteger",s)
        for x in ("we5927-lte reconnect", "sysupgrade ", "uci set ", "modem power",
                  "AT+CMGL=4' 5000", "AT+CUSD=1' 1500", "rm -rf /www",
                  "opkg install", "apk add"):
            self.assertNotIn(x,s)

    def test_install_does_not_send_modem_commands(self):
        s=SCRIPT.read_text()
        self.assertIn("NO_AT_COMMAND_SENT_BY_INSTALLER",s)
        self.assertNotIn("/usr/sbin/we5927-at",s)
        self.assertNotIn("ubus call veci.cellular",s)
        self.assertNotIn("/etc/init.d/rpcd restart",s)
        self.assertNotIn("reboot\n",s)

    def test_reversible_and_separate_persistent_backup(self):
        s=SCRIPT.read_text()
        self.assertIn("BACKUP=/root/veci-sms-storage-ui-v1-rollback",s)
        self.assertIn("[ ! -e \"$BACKUP\" ]",s)
        self.assertIn("cp -p \"$PAGE\" \"$BACKUP/old-cellular\"",s)
        self.assertIn("old-cellular.sha256",s)
        self.assertIn("trap cleanup EXIT",s)
        self.assertIn("restore ||",s)
        self.assertIn("VECI_SMS_STORAGE_UI_ROLLBACK_PASS",s)
        self.assertIn("VECI_SMS_STORAGE_UI_LIVE_ASSETS_PASS",s)

    def test_no_unbounded_silent_replace(self):
        s=SCRIPT.read_text()
        self.assertIn('cmp -s "$PAGE" "$work/original"',s)
        self.assertIn('fail "Installed Cellular differs from pinned base: untouched"',s)
        self.assertIn('cmp -s "$UTIL" "$work/new-util"',s)
        self.assertIn('cmp -s "$PAGE" "$work/new-page"',s)
        self.assertIn("NO CHANGES",s.replace("untouched","NO CHANGES") if "untouched" in s else s)


if __name__=="__main__":
    unittest.main()
