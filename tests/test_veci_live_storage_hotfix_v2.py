"""Offline checks for WE5927 reversible v2 SMS slot-counts hotfix."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts/veci-live-storage-hotfix-v2.sh"
V2 = ROOT / "scripts/veci-live-storage-v2"
V1 = ROOT / "scripts/veci-live-minimal"
RPC = V2 / "veci.cellular"
ACL = V2 / "veci-cellular-we5927.json"
HELPER = V2 / "veci-modem-capabilities"


class StorageV2Regression(unittest.TestCase):
    def test_shell_syntax(self):
        for file in (INSTALLER, RPC, HELPER):
            with self.subTest(file=file.name):
                p = subprocess.run(["sh", "-n", str(file)],
                                   capture_output=True, text=True)
                self.assertEqual(p.returncode, 0, p.stderr)

    def test_exact_source_and_sha256_pins(self):
        s = INSTALLER.read_text()
        self.assertRegex(s, r"(?m)^SOURCE_SHA=[0-9a-f]{40}$")
        self.assertIn("SOURCE_SHA=a880417be79c5a1e156c6c39023e6a905216f5fd", s)
        for path, name in ((RPC, "RPC_NEW"), (ACL, "ACL_NEW"), (HELPER, "HELPER_NEW"),
                           (V1 / "veci.cellular", "RPC_OLD"),
                           (V1 / "veci-cellular-we5927.json", "ACL_OLD"),
                           (V1 / "veci-modem-capabilities", "HELPER_OLD")):
            with self.subTest(sha=name):
                m = re.search(rf"(?m)^{name}=([0-9a-f]{{64}})$", s)
                self.assertIsNotNone(m)
                self.assertEqual(m.group(1), hashlib.sha256(path.read_bytes()).hexdigest())

    def test_preserves_contract_and_identity_boundaries(self):
        text = RPC.read_text()
        for method in ("status", "reconnect", "switchSim", "messagingCapabilities",
                       "messagingStorage"):
            self.assertIn(f'"{method}":', text)
        self.assertIn('"switchSim": { "sim": "String" }', text)
        self.assertIn("messagingStorage) messaging_storage ;;", text)
        self.assertNotIn("identity) identity ;;", text)
        self.assertNotIn("identityLive) identity_live ;;", text)

    def test_acl_only_adds_read_storage(self):
        a = json.loads(ACL.read_text())["veci-cellular-we5927"]
        self.assertEqual(a["read"]["ubus"]["veci.cellular"],
                         ["status", "messagingCapabilities", "messagingStorage"])
        self.assertEqual(a["write"]["ubus"]["veci.cellular"],
                         ["reconnect", "switchSim"])
        for forbidden in ("sendSms", "deleteSms", "ussdExecute", "identityLive"):
            self.assertNotIn(forbidden, str(a))

    def test_helper_has_single_readonly_storage_query_and_lock(self):
        s = HELPER.read_text()
        self.assertIn("'AT+CPMS?' 1500", s)
        self.assertIn("flock -n -x 9", s)
        self.assertIn("storage_parse", s)
        self.assertIn("storage) storage_query ;;", s)
        self.assertIn('[ "$name" != ttyUSB3 ]', s)
        for forbidden in ("AT+CMGL", "AT+CMGR", "AT+CMGS", "AT+CMGD",
                          "AT+CUSD=1", "uci set", "smsBody"):
            self.assertNotIn(forbidden, s)

    def test_installer_never_sends_modem_commands_or_flashes(self):
        s = INSTALLER.read_text()
        for forbidden in ("sysupgrade -", "reboot ", "AT+CMGR", "AT+CMGS",
                          "AT+CUSD=1", "uci set", "usermod"):
            self.assertNotIn(forbidden, s)
        self.assertIn("NO_AT_COMMAND_SENT_BY_INSTALLER", s)
        self.assertNotIn("/usr/sbin/we5927-at \"$at_port\"", s)
        self.assertIn("download veci-modem-capabilities", s)

    def test_legacy_status_and_methods_checked_pre_post(self):
        s = INSTALLER.read_text()
        self.assertIn("methods_ok || die \"baseline methods not registered\"", s)
        self.assertIn("status_ok || die \"baseline LTE status not healthy\"", s)
        self.assertIn("methods_ok || die \"legacy RPC method registration regressed\"", s)
        self.assertIn("status_ok || die \"LTE status regressed after RPC restart\"", s)
        self.assertIn('grep -q \'"messagingStorage":\'', s)
        self.assertIn('grep -Fq \'"switchSim":{"sim":"String"}\'', s)

    def test_two_separate_persistent_backups_no_clobber(self):
        s = INSTALLER.read_text()
        self.assertIn("BACKUP=/root/veci-storage-hotfix-rollback", s)
        self.assertIn("/root/veci-capability-hotfix-rollback/old-rpc", s)
        self.assertIn('[ ! -e "$BACKUP" ]', s)
        for marker in ("cp -p \"$RPC\" \"$BACKUP/rpc\"",
                       "cp -p \"$ACL\" \"$BACKUP/acl\"",
                       "cp -p \"$HELPER\" \"$BACKUP/helper\"",
                       "backup_valid || die"):
            self.assertIn(marker, s)

    def test_recovery_runs_on_failure_only(self):
        s = INSTALLER.read_text()
        for text in ('trap finish EXIT', 'trap \'exit 130\' INT TERM',
                     'changed=1', 'success=1', 'recover ||',
                     'V2_ROLLBACK_PASS', 'V2_LIVE_RPC_PASS'):
            self.assertIn(text, s)
        self.assertLess(s.index('changed=1'), s.index('install_one "$work/helper"'))
        self.assertLess(s.index('status_ok || die "LTE status regressed'), s.index('success=1'))

    def test_snapshot_remains_independent_of_current_firmware_helper(self):
        old = (V1 / "veci-modem-capabilities").read_text()
        new = HELPER.read_text()
        self.assertNotIn("storage) storage_query ;;", old)
        self.assertIn("storage) storage_query ;;", new)
        self.assertNotEqual(old, new)


if __name__ == "__main__":
    unittest.main()
