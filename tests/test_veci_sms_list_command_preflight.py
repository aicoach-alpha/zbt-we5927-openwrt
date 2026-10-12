"""Host-only sanitized 3GPP AT+CMGL=? test, never list physical SMS."""
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "scripts/veci-sms-list-command-preflight.sh"


def invoke_parser(response):
    s = FILE.read_text()
    f = re.search(r"(?ms)^parse_cmgl_test\(\) \{\n.*?^\}", s)
    assert f, "parser missing"
    cmd = "set -eu\n" + f.group() + "\nparse_cmgl_test\n"
    result = subprocess.run(["sh", "-c", cmd], input=response,
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


class SmsListTestOnly(unittest.TestCase):
    def test_shell_syntax(self):
        p = subprocess.run(["sh", "-n", str(FILE)],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_valid_response_with_older_range_accepted(self):
        s = "AT+CMGL=?\r\n+CMGL: (0-4)\r\nOK\r\n"
        self.assertEqual(invoke_parser(s), "accepted")

    def test_valid_response_with_list_accepted(self):
        s = '\r\n+CMGL: (0,1,2,3,4)\r\nOK\r\n'
        self.assertEqual(invoke_parser(s), "accepted")

    def test_does_not_confuse_command_echo_with_result(self):
        self.assertEqual(invoke_parser("AT+CMGL=?\r\nOK\r\n"), "unknown")
        self.assertEqual(invoke_parser("OK\r\n"), "unknown")

    def test_rejects_unexpected_sms_pdu_or_urc(self):
        for reply in (
            '+CMGL: 1,0,,2\r\n000011\r\nOK\r\n',
            '+CMGL: (0-4)\r\n+CMTI: "ME",1\r\nOK\r\n',
            '+CMGL: (0-4)\r\nOK\r\nOTPSECRET\r\n',
            '+CUSD: 0,"0031",72\r\n+CMGL: (0-4)\r\nOK\r\n',
        ):
            with self.subTest(reply=reply[:20]):
                self.assertEqual(invoke_parser(reply), "unknown")

    def test_truncation_and_duplicate_rejected(self):
        for reply in (
            "+CMGL: (0-4)\r\n",
            "+CMGL: (0-4)\r\n+CMGL: (0-4)\r\nOK\r\n",
            "+CMGL: (0-4)\r\nOK\r\nOK\r\n",
            "AT+CMGL=?\r\nAT+CMGL=?\r\n+CMGL: (0-4)\r\nOK\r\n",
        ):
            with self.subTest(reply=reply[:20]):
                self.assertEqual(invoke_parser(reply), "unknown")

    def test_no_setting_mutation_or_message_access_in_shell(self):
        src = FILE.read_text()
        self.assertIn("'AT+CMGL=?'", src)
        self.assertIn("flock -n -x 9", src)
        self.assertIn("/sys/class/tty/ttyUSB2/device", src)
        self.assertIn("05c6", src)
        self.assertIn("902e", src)
        for forbidden in ("'AT+CMGL=4'", "'AT+CMGL=0'",
                          "'AT+CMGR=", "'AT+CMGS=", "'AT+CMGF=0'",
                          "'AT+CUSD=", "sysupgrade ", "uci set ",
                          "reboot ", "logger ", "ttyUSB3"):
            self.assertNotIn(forbidden, src)

    def test_denies_extra_operands(self):
        self.assertIn('[ "$#" -eq 0 ] || exit 2', FILE.read_text())


if __name__ == "__main__":
    unittest.main()
