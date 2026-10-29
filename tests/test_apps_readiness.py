"""A Windows laptop can audit without changing any WE5927 service."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
import hashlib

ROOT=Path(__file__).resolve().parents[1]
SH=ROOT/'scripts/veci-apps-readiness.sh'
PS=ROOT/'scripts/veci-apps-readiness.ps1'

class AppsReadinessTests(unittest.TestCase):
    def test_shell_parses_and_stays_read_only(self):
        proc=subprocess.run(['sh','-n',str(SH)],capture_output=True,text=True)
        self.assertEqual(proc.returncode,0,proc.stderr)
        code=SH.read_text()
        for forbidden in ('uci set ', 'uci commit ', 'sysupgrade', 'apk add', 'apk del',
                          '/etc/init.d/', 'wifi reload', 'modem reconnect'):
            self.assertNotIn(forbidden,code)
        self.assertIn("APPS_INSTALL_GATE",code)
        self.assertIn("SIGNED_FEED_READY",code)
        self.assertIn("ACTION READ_ONLY_NO_ROUTER_CONFIG_CHANGES",code)
        self.assertNotIn('AT+CGSN',code)

    def test_windows_wrapper_pins_script_digest_and_never_installs(self):
        code=PS.read_text()
        sha=hashlib.sha256(SH.read_bytes()).hexdigest()
        self.assertIn(sha,code)
        self.assertIn('Get-FileHash',code)
        self.assertIn('StrictHostKeyChecking=ask',code)
        self.assertIn("scp.exe '-O'",code)
        self.assertIn('VeCI-audits',code)
        self.assertIn('APPS_INSTALL_GATE=SIGNED_FEED_READY',code)
        self.assertNotIn("apk add",code)
        self.assertNotIn("sysupgrade",code)

    def test_wrong_board_refuses_to_audit(self):
        with tempfile.TemporaryDirectory() as d:
            fake=Path(d)/'ubus'
            fake.write_text("#!/bin/sh\nprintf '{\\\"board_name\\\":\\\"not-we5927\\\"}'\n")
            fake.chmod(0o755)
            parser=Path(d)/'jsonfilter'
            parser.write_text("#!/bin/sh\nif [ \"$2\" = \"@.board_name\" ]; then echo other-model; else echo x; fi\n")
            parser.chmod(0o755)
            proc=subprocess.run(['sh',str(SH)],env={**os.environ,'PATH':d+':'+os.environ['PATH']},
                text=True,capture_output=True,timeout=8)
            self.assertEqual(proc.returncode,3)
            self.assertIn('RESULT=WRONG_ROUTER',proc.stdout)
            self.assertNotIn('APP_MANIFEST_GUEST',proc.stdout)

if __name__=='__main__': unittest.main()
