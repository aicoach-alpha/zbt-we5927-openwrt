"""Single targeted SMS delete AWK regression; synthetic AT only, no hardware.
Prevents the v1.5.4 'awk -v index' built-in keyword collision.
"""
import re
import subprocess
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"scripts/veci-sms-mifi-v153-staged/veci-sms-delete-one"

def body(name):
    data=SOURCE.read_text()
    pattern=rf"{name}\(\)\{{\s*awk -v slot_id=\"\$slot\" '([^']*)'"
    matched=re.search(pattern,data,re.S)
    if not matched:
        raise AssertionError(f"Missing safe AWK parser: {name}")
    return matched.group(1)

def feed(script,payload,index="3"):
    return subprocess.run(["awk","-v",f"slot_id={index}",script],
        input=payload,capture_output=True,text=True,timeout=3)

class DeleteParser(unittest.TestCase):
    def test_single_slot_recheck_pdu_exact(self):
        pdu="00040B912143658709F100000000000000000005C82293F904"
        tpdu=len(pdu)//2 - 1 - int(pdu[:2],16)
        raw=f"AT+CMGR=3\r\n+CMGR: 0,,{tpdu}\r\n{pdu}\r\nOK\r\n"
        parsed=feed(body("single_pdu"),raw)
        self.assertEqual(parsed.returncode,0,parsed.stderr)
        self.assertEqual(parsed.stdout.strip(),pdu)
        self.assertNotEqual(feed(body("single_pdu"),raw.replace(f"AT+CMGR=3",f"AT+CMGR=4")).returncode,0)
        self.assertNotEqual(feed(body("single_pdu"),raw.replace(pdu,pdu[:-2]+"GG")).returncode,0)

    def test_delete_ok_requires_one_exact_terminal(self):
        self.assertEqual(feed(body("delete_ok"),"AT+CMGD=3,0\r\nOK\r\n").returncode,0)
        self.assertNotEqual(feed(body("delete_ok"),"AT+CMGD=3,1\r\nOK\r\n").returncode,0)
        self.assertNotEqual(feed(body("delete_ok"),"AT+CMGD=3,0\r\nERROR\r\n").returncode,0)

    def test_only_single_delete_after_identity_match(self):
        data=SOURCE.read_text()
        self.assertIn(' [ "$current" = "$expected" ] || fail',data)
        self.assertIn('"AT+CMGD=$slot,0"',data)
        self.assertEqual(data.count("AT+CMGD="),2)  # response and actual command
        self.assertNotIn('awk -v index=',data)

if __name__=="__main__":
    unittest.main()
