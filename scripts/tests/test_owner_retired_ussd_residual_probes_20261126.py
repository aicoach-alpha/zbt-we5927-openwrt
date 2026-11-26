#!/usr/bin/env python3
"""Verify permanently retired USSD cannot be triggered through active modem probes."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
CAP = ROOT / "source/veci-cellular-we5927/files/usr/libexec/veci-modem-capabilities"
PAR = ROOT / "source/veci-core/veci/js/lib/modem-messages.js"
AT = ROOT / "source/we5927-lte/src/we5927-at.c"

class RetiredUssdProbeTests(unittest.TestCase):
    def test_no_ussd_probe_or_response_in_modem_capabilities(self):
        src = CAP.read_text()
        self.assertNotIn("AT+CUSD", src)
        self.assertNotIn("ussd", src.lower())
        for cmd in ("AT+CMGF=?", "AT+CPMS=?", "AT+CNMI=?"):
            self.assertIn(cmd, src)
        subprocess.run(["sh", "-n", str(CAP)], check=True)

    def test_no_reusable_decoder_in_legacy_js(self):
        src = PAR.read_text()
        self.assertNotIn("ussd", src.lower())
        self.assertNotIn("CUSD", src)

    def test_guard_against_unsafe_native_at_command_remains(self):
        self.assertIn('!strncasecmp(cmd,"AT+CUSD",7)', AT.read_text())

if __name__ == "__main__":
    unittest.main()
