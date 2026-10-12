"""WE5927 SMS/USSD AT test command diagnostics: NO modem or carrier traffic."""
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"source/veci-cellular-we5927"
HELPER=BASE/"files/usr/libexec/veci-modem-capabilities"
RPC=BASE/"files/usr/libexec/rpcd/veci.cellular"
ACL=BASE/"files/usr/share/rpcd/acl.d/veci-cellular-we5927.json"
LTE=ROOT/"source/we5927-lte/files/usr/sbin/we5927-lte"

def function(name):
    m=re.search(r"(?ms)^"+re.escape(name)+r"\(\) \{\n.*?^\}",HELPER.read_text())
    if not m: raise AssertionError("missing: "+name)
    return m.group()

class ModemCapabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir=Path(self.tmp.name)
        self.bin=self.dir/"fake-at"
        self.bin.write_text('''#!/bin/sh
case "$2" in
  'AT+CMGF=?') printf '\\r\\n+CMGF: (0,1)\\r\\n\\r\\nOK\\r\\n' ;;
  'AT+CPMS=?') printf '\\r\\n+CPMS: ("SM","ME")\\r\\nOK\\r\\n' ;;
  'AT+CNMI=?') printf '\\r\\nERROR\\r\\n' ;;
  'AT+CUSD=?') printf '\\r\\ngarbled\\r\\nOK\\r\\n' ;;
  *) printf 'BAD_CMD\\n'; exit 4 ;;
esac
''')
        self.bin.chmod(0o700)
        self.lock=self.dir/"modem.lock"

    def run_shell(self,script):
        return subprocess.run(["sh","-c",script],capture_output=True,text=True,timeout=7)

    def probe_script(self):
        src="\n".join(function(n) for n in ("unavailable","test_at","probe_capabilities"))
        src=src.replace("/usr/sbin/we5927-at",str(self.bin))
        src=src.replace("/var/lock/we5927-at.lock",str(self.lock))
        # This test NEVER probes a real serial device. Mock only find_at_port.
        return "set -eu\nfind_at_port() { printf '/dev/null\\n'; }\n"+src+"\nprobe_capabilities\n"

    def test_source_and_provider_are_valid_shell(self):
        for p in (HELPER,RPC):
            with self.subTest(file=p.name):
                r=subprocess.run(["sh","-n",str(p)],capture_output=True,text=True)
                self.assertEqual(r.returncode,0,r.stderr)

    def test_locked_mock_probe_returns_only_supported_rejected_or_unknown(self):
        result=self.run_shell(self.probe_script())
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout)
        self.assertTrue(data["ok"])
        self.assertEqual(data["state"],"probed")
        self.assertEqual(data["source"],"read_only_at_test")
        self.assertEqual(data["sms_mode"],"supported")
        self.assertEqual(data["sms_storage"],"supported")
        self.assertEqual(data["sms_notifications"],"rejected")
        self.assertEqual(data["ussd"],"unknown")
        self.assertNotIn("AT+",result.stdout)
        self.assertNotIn("+CPMS:",result.stdout)

    def test_busy_lock_never_waits_or_sends_a_command(self):
        fd=os.open(self.lock,os.O_CREAT|os.O_RDWR,0o600)
        self.addCleanup(os.close,fd)
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        result=self.run_shell(self.probe_script())
        self.assertEqual(result.returncode,0,result.stderr)
        status=json.loads(result.stdout)
        self.assertFalse(status["ok"])
        self.assertEqual(status["reason"],"modem_busy")
        self.assertEqual(status["ussd"],"not_tested")

    def test_bad_query_does_not_produce_supported(self):
        fake=str(self.bin)
        src=function("test_at").replace("/usr/sbin/we5927-at",fake)
        result=self.run_shell('at_port=/dev/null\n'+src+'\ntest_at "AT+INVALID" "+CMGF:"\n')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),"unavailable")

    def test_only_allowlisted_3gpp_test_commands_are_sent(self):
        source=HELPER.read_text()
        cmd=re.findall(r'test_at\s+[\x27"]([^"\x27]+)[\x27"]',source)
        self.assertEqual(cmd,["AT+CMGF=?","AT+CPMS=?","AT+CNMI=?","AT+CUSD=?"])
        self.assertNotRegex(source,r'AT\+(CMGS|CMGR|CMGL|CMGD|CUSD=1|CPMS=[^?])')
        self.assertIn("we5927-at.lock",source)
        self.assertIn("flock -n -x 9",source)
        self.assertIn("*/1-1:1.4/*",source)
        self.assertIn("/dev/ttyUSB3) return 1",source)

    def test_unrecognized_rpc_methods_cannot_send_sms(self):
        rpc=RPC.read_text()
        self.assertIn('"messagingCapabilities": {}',rpc)
        self.assertIn("messagingCapabilities) messaging_capabilities",rpc)
        self.assertNotIn('"sendSms"',rpc)
        self.assertNotIn('"ussdExecute"',rpc)
        self.assertIn("/usr/libexec/veci-modem-capabilities probe",rpc)

    def test_acl_allows_read_probe_but_no_sms_or_ussd_write(self):
        a=json.loads(ACL.read_text())["veci-cellular-we5927"]
        self.assertIn("messagingCapabilities",a["read"]["ubus"]["veci.cellular"])
        self.assertNotIn("messagingCapabilities",a["write"]["ubus"]["veci.cellular"])
        self.assertNotIn("sendSms",str(a))
        self.assertNotIn("ussdExecute",str(a))

    def test_general_and_indonesia_package_share_one_diagnostic_helper(self):
        mk=(BASE/"Makefile").read_text()
        self.assertIn("veci-modem-capabilities",mk)
        self.assertIn("+we5927-lte",mk)
        self.assertNotIn("python3",mk)
        self.assertNotIn("nodejs",mk)
        selector=(ROOT/"scripts/prepare-veci.sh").read_text()
        self.assertIn("veci-cellular-we5927",selector)

if __name__=="__main__":
    unittest.main()
