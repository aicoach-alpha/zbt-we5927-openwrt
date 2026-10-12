"""Host-only masked AT+CPMS? storage stats: no real modem or SMS content."""
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "source/veci-cellular-we5927/files"
HELPER = BASE / "usr/libexec/veci-modem-capabilities"
RPC = BASE / "usr/libexec/rpcd/veci.cellular"
ACL = BASE / "usr/share/rpcd/acl.d/veci-cellular-we5927.json"


def get_function(name):
    m = re.search(r"(?ms)^" + re.escape(name) + r"\(\) \{\n.*?^\}",
                  HELPER.read_text())
    assert m is not None, f"missing {name}"
    return m.group()


class ReadOnlyStorage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.response = self.folder / "reply.txt"
        self.commands = self.folder / "AT.log"
        self.lock = self.folder / "modem.lock"
        self.fake = self.folder / "at-mock"
        self.fake.write_text("""#!/bin/sh
[ "$2" = 'AT+CPMS?' ] || exit 7
[ "$3" = 1500 ] || exit 8
printf '%s\n' "$2" >> "$AT_MOCK_LOG"
cat "$AT_MOCK_RESPONSE"
""")
        self.fake.chmod(0o700)
        self.reply('AT+CPMS?\r\n+CPMS: "SM",2,30,"SM",2,30,"SM",2,30\r\nOK\r\n')

    def reply(self, text):
        self.response.write_bytes(text.encode())

    def run_storage(self, extra_env=None):
        body = "\n".join(get_function(n) for n in (
            "storage_parse", "storage_error", "storage_query"))
        body = body.replace("/usr/sbin/we5927-at", str(self.fake))
        body = body.replace("/var/lock/we5927-at.lock", str(self.lock))
        shell = ('set -eu\nfind_at_port() { printf "/dev/null\\n"; }\n'
                 + body + "\nstorage_query\n")
        env = os.environ.copy()
        env["AT_MOCK_RESPONSE"] = str(self.response)
        env["AT_MOCK_LOG"] = str(self.commands)
        if extra_env:
            env.update(extra_env)
        return subprocess.run(["sh", "-c", shell], env=env,
                              text=True, capture_output=True, timeout=5)

    def one_query(self, response):
        self.reply(response)
        result = self.run_storage()
        self.assertEqual(result.returncode, 0, result.stderr)
        obj = json.loads(result.stdout)
        self.assertNotIn("+CPMS:", result.stdout)
        self.assertNotIn("AT+CPMS?", result.stdout)
        return obj

    def test_readonly_command_returns_numeric_counts(self):
        r = self.one_query('AT+CPMS?\r\n+CPMS: "SM",2,30,"SM",2,30,"SM",2,30\r\nOK\r\n')
        self.assertEqual(r, {"ok": True, "state": "queried",
                             "source": "read_only_at_cpms",
                             "memory": "SM", "used": 2, "total": 30})
        self.assertEqual(self.commands.read_text().strip(), "AT+CPMS?")

    def test_blank_or_no_echo_accepted(self):
        r = self.one_query('\r\n+CPMS: "ME",0,255,"SM",0,20,"SM",0,20\r\n\r\nOK\r\n')
        self.assertEqual((r["memory"], r["used"], r["total"]), ("ME",0,255))

    def test_spaces_and_leading_zeros_normalized(self):
        r = self.one_query(' +CPMS: "SM", 002, 030, "ME",0,8, "ME",0,8\r\nOK\r\n')
        self.assertEqual((r["used"],r["total"]), (2,30))

    def test_data_after_ok_rejected(self):
        r = self.one_query('+CPMS: "SM",0,20,"SM",0,20,"SM",0,20\r\nOK\r\n+CUSD: "secret"\r\n')
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "invalid_response")

    def test_duplicate_storage_response_rejected(self):
        row = '+CPMS: "SM",0,20,"SM",0,20,"SM",0,20\r\n'
        r = self.one_query(row + row + 'OK\r\n')
        self.assertFalse(r["ok"])

    def test_unsolicited_notification_rejected(self):
        r = self.one_query('+CMTI: "SM",1\r\n+CPMS: "SM",0,20,"SM",0,20,"SM",0,20\r\nOK\r\n')
        self.assertFalse(r["ok"])

    def test_incomplete_reply_rejected(self):
        r = self.one_query('+CPMS: "SM",0,20,"SM",0,20,"SM",0,20\r\n')
        self.assertFalse(r["ok"])

    def test_only_ok_without_storage_rejected(self):
        r = self.one_query('OK\r\n')
        self.assertFalse(r["ok"])

    def test_error_not_a_valid_count(self):
        r = self.one_query('ERROR\r\n')
        self.assertFalse(r["ok"])

    def test_reject_invalid_numeric_data(self):
        cases = [
            '+CPMS: "SM",-1,20,"SM",0,20,"SM",0,20\r\nOK\r\n',
            '+CPMS: "SM",21,20,"SM",0,20,"SM",0,20\r\nOK\r\n',
            '+CPMS: "SM",1,999999,"SM",0,20,"SM",0,20\r\nOK\r\n',
            '+CPMS: "SM",NaN,20,"SM",0,20,"SM",0,20\r\nOK\r\n',
            '+CPMS: "SM",1,20,"SM",0,20\r\nOK\r\n',
            '+CPMS: "SM",1,20,"SM",0,20,"SM",0,20,"SM",0,20\r\nOK\r\n',
            '+CPMS: "SM",1,20,"SM",50,20,"SM",0,20\r\nOK\r\n',
        ]
        for c in cases:
            with self.subTest(line=c[:42]):
                r = self.one_query(c)
                self.assertFalse(r["ok"])

    def test_reject_sms_body_injection(self):
        r = self.one_query('+CPMS: "SM",1,20,"SM",0,20,"SM",0,20\r\nSMS_OTP_12345\r\nOK\r\n')
        self.assertFalse(r["ok"])
        self.assertNotIn("SMS_OTP", json.dumps(r))

    def test_reject_malicious_memory_label(self):
        r = self.one_query('+CPMS: "SMS\\nOTP",1,20,"SM",0,20,"SM",0,20\r\nOK\r\n')
        self.assertFalse(r["ok"])

    def test_concurrent_lock_prevents_AT(self):
        fd = os.open(self.lock, os.O_CREAT | os.O_RDWR, 0o600)
        self.addCleanup(os.close, fd)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        r = self.run_storage()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["reason"], "modem_busy")
        self.assertFalse(self.commands.exists())

    def test_exposes_no_secret_content_or_mutating_at(self):
        src = HELPER.read_text()
        self.assertIn("'AT+CPMS?' 1500", src)
        self.assertIn("storage_parse", src)
        self.assertNotIn("AT+CMGL", src)
        self.assertNotIn("AT+CMGR", src)
        self.assertNotIn("AT+CMGS", src)
        self.assertNotIn("AT+CMGD", src)
        self.assertNotIn("AT+CUSD=1", src)

    def test_shell_parses_and_cli_requires_one_argument(self):
        p = subprocess.run(["sh","-n",str(HELPER)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn("storage) storage_query ;;", HELPER.read_text())


if __name__ == "__main__":
    unittest.main()
