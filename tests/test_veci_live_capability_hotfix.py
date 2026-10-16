"""Static/offline safeguards for WE5927 operator-run partial capabilities hotfix."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOTFIX = ROOT / "scripts/veci-live-capability-hotfix.sh"
RPC = ROOT / "scripts/veci-live-minimal/veci.cellular"
ACL = ROOT / "scripts/veci-live-minimal/veci-cellular-we5927.json"
HELPER = ROOT / "source/veci-cellular-we5927/files/usr/libexec/veci-modem-capabilities"
PINNED_HELPER = ROOT / "scripts/veci-live-minimal/veci-modem-capabilities"


class PartialReleaseContract(unittest.TestCase):
    def test_script_syntax(self):
        for p in (HOTFIX, RPC, HELPER, PINNED_HELPER):
            r = subprocess.run(["sh", "-n", str(p)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f"{p}: {r.stderr}")

    def test_pinned_source_manifest_sha256(self):
        script = HOTFIX.read_text()
        files = (
            (RPC, "RPC_SHA"),
            (PINNED_HELPER, "HELPER_SHA"),
            (ACL, "ACL_SHA"),
        )
        for p, symbol in files:
            match = re.search(r"^" + symbol + r"=([0-9a-f]{64})$", script, re.M)
            self.assertIsNotNone(match, symbol)
            actual = hashlib.sha256(p.read_bytes()).hexdigest()
            self.assertEqual(actual, match.group(1), str(p))
        self.assertRegex(script, r"(?m)^SOURCE_SHA=[0-9a-f]{40}$")
        self.assertNotIn("SOURCE_SHA=dev", script)
        self.assertIn("probe) probe_capabilities", PINNED_HELPER.read_text())
        self.assertNotIn("AT+CPMS?' 1500", PINNED_HELPER.read_text())
        self.assertIn("check_sha \"$work/rpc\" \"$RPC_SHA\"", script)
        self.assertIn("check_sha \"$work/helper\" \"$HELPER_SHA\"", script)
        self.assertIn("check_sha \"$work/acl\" \"$ACL_SHA\"", script)

    def test_reuses_original_sim_schema_and_methods(self):
        src = RPC.read_text()
        self.assertIn('"status": {}', src)
        self.assertIn('"messagingCapabilities": {}', src)
        self.assertIn('"switchSim": { "sim": "String" }', src)
        self.assertIn('status) status ;;', src)
        self.assertIn('reconnect) reconnect ;;', src)
        self.assertIn('switchSim) switch_sim ;;', src)
        self.assertIn('messagingCapabilities) messaging_capabilities ;;', src)
        self.assertNotIn('identity) identity ;;', src)
        self.assertNotIn('identityLive) identity_live ;;', src)

    def test_acl_no_new_imei_permission_or_write_capability(self):
        a = json.loads(ACL.read_text())["veci-cellular-we5927"]
        self.assertEqual(a["read"]["ubus"]["veci.cellular"],
                         ["status", "messagingCapabilities"])
        self.assertEqual(a["write"]["ubus"]["veci.cellular"],
                         ["reconnect", "switchSim"])
        self.assertNotIn("identityLive", str(a))
        self.assertNotIn("sendSms", str(a))
        self.assertNotIn("ussdExecute", str(a))

    def test_probe_is_explicit_and_uses_fixed_at_tests(self):
        src = HELPER.read_text()
        sent = re.findall(r'test_at\s+[\'"]([^\'"]+)[\'"]', src)
        self.assertEqual(sent, ["AT+CMGF=?", "AT+CPMS=?",
                                "AT+CNMI=?", "AT+CUSD=?"])
        self.assertIn("flock -n -x 9", src)
        self.assertIn("1.4/", src)
        self.assertIn('[ "$name" != ttyUSB3 ]', src)
        self.assertNotIn("uci -q get we5927_lte.main.at_port", src)

    def test_auto_rollback_happens_on_registration_failure(self):
        s = HOTFIX.read_text()
        for marker in ("trap cleanup EXIT", "changed=1", "recover_files",
                       "/etc/init.d/rpcd restart",
                       "LIVE_RPC_REGISTRATION_PASS",
                       "NO_AT_COMMAND_SENT_BY_INSTALLER",
                       "BACKUP=/root/veci-capability-hotfix-rollback"):
            self.assertIn(marker, s)
        self.assertIn('[ ! -e "$BACKUP" ]', s)
        self.assertIn("source-commit", s)
        self.assertIn("NO_AT_COMMAND_SENT_BY_INSTALLER", s)
        self.assertNotIn("sysupgrade ", s)
        self.assertNotIn("AT+CMGR", s)
        self.assertNotIn("AT+CMGS", s)
        self.assertNotIn("AT+CUSD=1", s)
        self.assertNotIn("uci set", s)

    def test_existing_and_updated_status_health_are_rollback_gates(self):
        s = HOTFIX.read_text()
        self.assertIn('baseline="$(ubus call veci.cellular status', s)
        self.assertIn('current_status="$(ubus call veci.cellular status', s)
        self.assertIn('LTE status response invalid after patch', s)
        self.assertLess(s.index('current_status="$(ubus call'),
                        s.index('success=1'))

    def test_download_source_file_paths_are_pinned(self):
        s = HOTFIX.read_text()
        self.assertIn("fetch scripts/veci-live-minimal/veci.cellular", s)
        self.assertIn("fetch scripts/veci-live-minimal/veci-cellular-we5927.json", s)
        self.assertIn("source/veci-cellular-we5927/files/usr/libexec/veci-modem-capabilities", s)
        self.assertIn("wget -q -O", s)
        self.assertNotIn("raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/dev", s)


if __name__ == "__main__":
    unittest.main()
