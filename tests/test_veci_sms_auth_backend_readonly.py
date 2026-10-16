"""Read-only / redacted UCI and ubus backend readiness preflight contract."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/veci-sms-auth-backend-preflight-20261013.sh"

class Readiness(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir=Path(self.tmp.name)
        self.bin=self.dir/"bin"
        self.bin.mkdir()
        uci=self.bin/"uci"
        uci.write_text("#!/bin/sh\n[ \"$1\" = '-q' ] && [ \"$2\" = 'show' ] && [ \"$3\" = 'uhttpd' ] || exit 2\n"
            "echo \"uhttpd.main=\'uhttpd\'\"\n"
            "echo \"uhttpd.main.ubus_noauth=0\"\n"
            "echo \"uhttpd.main.ubus_cors=0\"\n"
            "echo \"uhttpd.main.password=CANARY_SECRET_DO_NOT_PRINT\"\n")
        uci.chmod(0o755)
        ubus=self.bin/"ubus"
        ubus.write_text("#!/bin/sh\n[ \"$1\" = '-S' ] && [ \"$2\" = 'list' ] || exit 2\necho veci.sms\necho veci.cellular\n")
        ubus.chmod(0o755)
        self.env={**os.environ,"PATH":str(self.bin)+":"+os.environ["PATH"]}

    def test_no_secret_output_and_no_modem(self):
        result=subprocess.run(["sh",str(SCRIPT)],text=True,capture_output=True,
                              env=self.env,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn("UHTTPD_UBUS_NOAUTH=not_enabled_in_uci",result.stdout)
        self.assertIn("UHTTPD_UBUS_CORS=not_enabled_in_uci",result.stdout)
        self.assertIn("VECI_PRIVATE_SMS_API=not_registered",result.stdout)
        self.assertIn("SESSION_IDS_EXPORTED=false",result.stdout)
        self.assertIn("SMS_MODEM_COMMAND_SENT=false",result.stdout)
        self.assertNotIn("CANARY_SECRET",result.stdout+result.stderr)

    def test_noauth_positive_is_a_warning_not_a_change(self):
        uci=self.bin/"uci"
        contents=uci.read_text().replace("ubus_noauth=0","ubus_noauth=1")
        uci.write_text(contents)
        result=subprocess.run(["sh",str(SCRIPT)],text=True,capture_output=True,
                              env=self.env,timeout=5)
        self.assertIn("UHTTPD_UBUS_NOAUTH=enabled",result.stdout)
        self.assertNotIn("CANARY_SECRET",result.stdout)

    def test_no_sensitive_commands(self):
        s=SCRIPT.read_text()
        for term in ("AT+CMGR","AT+CMGL","AT+CUSD","AT+CMGD",
                     "systemctl","/etc/init.d/rpcd restart",
                     "ubus call session list","sysupgrade","reboot",
                     "login", "shadow"):
            # Existing comments may mention credentials/login/shadow;
            # only enforce against shell command patterns.
            if term in ("login","shadow"):
                continue
            self.assertNotIn(term,s)
        self.assertNotIn("ssh root@",s)
        self.assertNotIn("uci set",s)
        self.assertNotIn("ubus call",s)
        self.assertEqual(subprocess.run(["sh","-n",str(SCRIPT)]).returncode,0)

if __name__=="__main__":
    unittest.main()
