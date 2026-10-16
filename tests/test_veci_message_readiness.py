"""No-modem regression for W907 no-write SMS mode/charset UAT helper."""
import re
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"scripts/veci-messaging-readiness-ondevice.sh"

def extract(name):
    m=re.search(r"(?ms)^"+re.escape(name)+r"\(\) \{\n.*?^\}",SRC.read_text())
    if not m:
        raise AssertionError("missing function "+name)
    return m.group()

def parse(name,raw):
    cmd="set -eu\n"+extract(name)+"\n"+name+"\n"
    r=subprocess.run(["sh","-c",cmd],input=raw,text=True,capture_output=True,timeout=5)
    if r.returncode:
        raise AssertionError(r.stderr)
    return r.stdout.strip()

class ReadinessSafety(unittest.TestCase):
    def test_shell_syntax(self):
        p=subprocess.run(["sh","-n",str(SRC)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)

    def test_mode_pdu_and_text(self):
        for expected,number in (("pdu","0"),("text","1")):
            with self.subTest(mode=expected):
                raw=f"AT+CMGF?\r\n+CMGF: {number}\r\nOK\r\n"
                self.assertEqual(parse("parse_cmgf",raw),expected)

    def test_mode_no_echo_is_supported(self):
        self.assertEqual(parse("parse_cmgf","\r\n+CMGF: 0\r\nOK\r\n"),"pdu")

    def test_mode_malformed_duplicate_urc_fails_closed(self):
        for raw in ("OK\r\n","+CMGF: 0\r\n",
                    "+CMGF: 0\r\n+CMGF: 1\r\nOK\r\n",
                    '+CMTI: "ME",5\r\n+CMGF: 0\r\nOK\r\n',
                    "+CMGF: 9\r\nOK\r\n",
                    "+CMGF: 0\r\nOK\r\n+CUSD: 1\r\n",
                    "AT+CMGS=123\r\n+CMGF: 1\r\nOK\r\n"):
            with self.subTest(raw=raw[:30]):
                self.assertEqual(parse("parse_cmgf",raw),"unknown")

    def test_charset_known(self):
        for name in ("GSM","IRA","UCS2","UTF-8","HEX"):
            with self.subTest(charset=name):
                self.assertEqual(parse("parse_cscs",f'+CSCS: "{name}"\r\nOK\r\n'),name)

    def test_charset_unknown_is_sanitized(self):
        self.assertEqual(parse("parse_cscs",'+CSCS: "PCCP437"\r\nOK\r\n'),"other")
        self.assertEqual(parse("parse_cscs",'+CSCS: "SECRETOTP"\r\nOK\r\n'),"other")
        self.assertEqual(parse("parse_cscs",'+CSCS: "GSM"\r\n+CUSD: 1\r\nOK\r\n'),"unknown")
        self.assertEqual(parse("parse_cscs",'+CSCS: "GSM"\r\n'),"unknown")

    def test_no_generic_at_or_unverified_port_fallback(self):
        s=SRC.read_text()
        self.assertIn("zbtlink,zbt-we5927",s)
        self.assertIn("/sys/class/tty/ttyUSB2/device",s)
        self.assertIn("05c6",s)
        self.assertIn("902e",s)
        self.assertIn("1.4/ttyUSB2",s)
        self.assertIn("flock -n -x 9",s)
        self.assertIn("'AT+CMGF?'",s)
        self.assertIn("'AT+CSCS?'",s)
        for term in ("AT+CMGL", "AT+CMGR", "AT+CMGS",
                     "AT+CUSD", "AT+CMGF=", "AT+CSCS=", "ttyUSB3",
                     "sysupgrade", "uci set", "reboot", "SMS_OTP"):
            self.assertNotIn(term,s)

    def test_no_sensitive_transcripts_returned(self):
        s=SRC.read_text()
        self.assertIn("unset raw",s)
        self.assertIn('printf \'{"ok":true,"source":"read_only_at"',s)
        self.assertIn("sms_mode",s)
        self.assertIn("charset",s)
        self.assertNotIn('echo "$raw"',s)
        self.assertNotIn("logger",s)

if __name__=="__main__":
    unittest.main()
