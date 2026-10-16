"""Offline only: validate privacy and strict PDU metadata parser.
No physical AT access, no SMS read, no SSH or OpenWrt dependencies.
"""
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/veci-sms-inbox-index-preview.sh"


def parser_function(name):
    text = SCRIPT.read_text()
    match = re.search(r"(?ms)^" + re.escape(name) + r"\(\) \{\n.*?^\}", text)
    assert match, f"missing {name}"
    return match.group()


def parse_sms(response):
    command = "set -eu\n" + parser_function("parse_list") + "\nparse_list\n"
    return subprocess.run(
        ["sh", "-c", command],
        input=response, text=True, capture_output=True, timeout=5
    )


def entry(index, state=0, pdu="000011"):
    assert len(pdu) % 2 == 0
    return f"+CMGL: {index},{state},,{len(pdu)//2-1}\r\n{pdu}\r\n"


class InboxPreviewOffline(unittest.TestCase):
    def test_shell_syntax(self):
        p = subprocess.run(["sh", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_complete_two_message_list_output_no_contents(self):
        wire = "AT+CMGL=4\r\n" + entry(2,0) + entry(8,1) + "OK\r\n"
        output = parse_sms(wire)
        self.assertEqual(output.returncode, 0, output.stderr)
        self.assertEqual(json.loads(output.stdout), {
            "ok": True, "source": "on_demand_cmgl",
            "side_effect_acknowledged": True, "count": 2,
            "messages": [
                {"index": 2, "status": 0, "tpdu_octets": 2},
                {"index": 8, "status": 1, "tpdu_octets": 2}
            ]
        })
        self.assertNotIn("000011", output.stdout)
        self.assertNotIn("+CMGL:", output.stdout)

    def test_empty_inbox(self):
        output = parse_sms("AT+CMGL=4\r\nOK\r\n")
        self.assertEqual(output.returncode, 0)
        self.assertEqual(json.loads(output.stdout)["messages"], [])

    def test_valid_smsc_offset(self):
        # SMSC length 2, two SMSC bytes, and two TPDU bytes.
        output = parse_sms("+CMGL: 1,0,,2\r\n0211220011\r\nOK\r\n")
        self.assertEqual(output.returncode, 0, output.stderr)
        self.assertEqual(json.loads(output.stdout)["messages"][0]["tpdu_octets"], 2)

    def test_synthetic_secret_never_emitted(self):
        secret = "004F5450363931323334"
        output = parse_sms(entry(1,0,secret) + "OK\r\n")
        self.assertEqual(output.returncode, 0, output.stderr)
        self.assertNotIn(secret, output.stdout)
        self.assertNotIn("OTP", output.stdout)
        self.assertEqual(json.loads(output.stdout)["count"], 1)

    def test_duplicate_indices_rejected_entirely(self):
        output = parse_sms(entry(1,0) + entry(1,1) + "OK\r\n")
        self.assertNotEqual(output.returncode, 0)
        self.assertFalse(output.stdout.strip())

    def test_corrupt_status_and_length(self):
        for wire in (
            "+CMGL: 2,5,,2\r\n000011\r\nOK\r\n",
            "+CMGL: 2,0,,3\r\n000011\r\nOK\r\n",
            "+CMGL: 2,0,,0\r\n000011\r\nOK\r\n",
            "+CMGL: 2,0,,2\r\n00ZZ11\r\nOK\r\n",
            "+CMGL: 2,0,,2\r\nFF0011\r\nOK\r\n",
            '+CMGL: 2,"REC UNREAD","+628"\r\nAB\r\nOK\r\n',
            "+CMGL: 999999,0,,2\r\n000011\r\nOK\r\n",
        ):
            with self.subTest(prefix=wire[:25]):
                result = parse_sms(wire)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(result.stdout.strip())

    def test_truncated_or_error_no_partial_results(self):
        for wire in (
            entry(1),
            entry(1) + "ERROR\r\n",
            entry(1) + "+CMS ERROR: 321\r\n",
            "+CMGL: 1,0,,2\r\n",
            "O",
            entry(1) + "OK\r\n+CMTI: \"ME\",2\r\n",
        ):
            with self.subTest(prefix=wire[:25]):
                r = parse_sms(wire)
                self.assertNotEqual(r.returncode, 0)
                self.assertFalse(r.stdout.strip())

    def test_reject_unsolicited_cusd_and_cmt(self):
        for signal in ('+CMTI: "ME",3', '+CUSD: 0,"0031",72',
                       '+CMT: ,2', "RING"):
            r = parse_sms(signal+"\r\n"+entry(1)+"OK\r\n")
            self.assertNotEqual(r.returncode, 0)
            self.assertFalse(r.stdout.strip())

    def test_limit_16_messages_and_pdu_budget(self):
        r = parse_sms("".join(entry(i) for i in range(16)) + "OK\r\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["count"], 16)
        r = parse_sms("".join(entry(i) for i in range(17)) + "OK\r\n")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(r.stdout.strip())
        r = parse_sms(entry(1,0,"00" + "11" * 257) + "OK\r\n")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(r.stdout.strip())

    def test_mode_parser_validates_pdu_only(self):
        cmd = "set -eu\n" + parser_function("parse_mode") + "\nparse_mode\n"
        for reply, expect in [
            ("AT+CMGF?\r\n+CMGF: 0\r\nOK\r\n","pdu"),
            ("+CMGF: 1\r\nOK\r\n","unknown"),
            ("+CMGF: 0\r\n+CMGF: 1\r\nOK\r\n","unknown"),
        ]:
            r = subprocess.run(["sh","-c",cmd],input=reply,text=True,
                               capture_output=True,timeout=5)
            self.assertEqual(r.stdout.strip(),expect)

    def test_flags_usb_identity_and_shared_lock(self):
        text = SCRIPT.read_text()
        self.assertIn('"--show-indices-only"', text)
        self.assertIn('"--ack-unread-may-be-marked-read"', text)
        self.assertIn('[ "$(id -u)" -eq 0 ]', text)
        self.assertIn("05c6", text)
        self.assertIn("902e", text)
        self.assertIn("1.4/ttyUSB2", text)
        self.assertIn("flock -n -x 9", text)
        self.assertLess(text.index("flock -n -x 9"), text.index('port="$(readlink -f'))
        self.assertIn("'AT+CMGF?'", text)
        self.assertIn("'AT+CMGL=4'", text)
        for forbidden in ("AT+CMGS=", "AT+CUSD=", "AT+CMGD=", 
                          "sysupgrade ", "uci set ", "reboot "):
            self.assertNotIn(forbidden, text)

    def test_no_auto_polling_or_otp_output(self):
        s = SCRIPT.read_text()
        self.assertNotIn("logger ", s)
        self.assertNotIn("curl ", s)
        self.assertNotIn("wget ", s)
        self.assertNotIn("crontab", s)
        self.assertNotIn('echo "$raw"', s)
        self.assertIn('unset raw', s)
        self.assertIn("side_effect_acknowledged", s)


if __name__ == "__main__":
    unittest.main()
