"""WE5927 physical 6357B original: exact captured source and safe, UI-only SMS count delta."""
from pathlib import Path
import hashlib
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "scripts/veci-sms-ui-live-captured-20261012/cellular.js"
ORIGINAL = "0a4e78d5368806b31441612b8979ab7b2ac8f425890cfd89104f969accd8ee18"
EXPECTED = "2deb013e6ccf433b9c3abc3d7f02aafb33739dd1b5b5f222d4de501865314d40"

class CapturedExactOverlay(unittest.TestCase):
    def test_exact_expected_patch_digest(self):
        data = PAGE.read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), EXPECTED)
        self.assertEqual(len(data), 8352)

    def test_syntax(self):
        p = subprocess.run(["node", "--check", str(PAGE)], text=True, capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_two_isolated_insertions_revert_to_captured_original(self):
        code = PAGE.read_text()
        panel_start = code.index('\t\t\t<section class="panel" aria-labelledby="cellular-sms-count-title">')
        panel_end = code.index('\t\t\t<div class="notice-card">', panel_start)
        self.assertEqual(code[panel_end-1], '\n')
        code = code[:panel_start] + code[panel_end:]
        handler_start = code.index("\t\t// The existing v2 endpoint reads AT+CPMS? only.")
        handler_end = code.index("\t\tconst reconnect = root.querySelector('#cellular-reconnect');", handler_start)
        code = code[:handler_start] + code[handler_end:]
        self.assertEqual(hashlib.sha256(code.encode()).hexdigest(), ORIGINAL)

    def test_no_modem_or_sms_body_access(self):
        s=PAGE.read_text()
        self.assertEqual(s.count("messagingStorage"), 1)
        self.assertEqual(s.count("smsCountButton?.addEventListener('click'"), 1)
        self.assertIn("read_only_at_cpms", s)
        self.assertIn("SMS Inbox is not enabled yet",s)
        self.assertIn("Number.isSafeInteger",s)
        for forbidden in ("AT+CMGL=", "AT+CMGR=", "AT+CUSD=", "AT+CMGS=", "eval(", "new Function("):
            self.assertNotIn(forbidden,s)

    def test_controls_retained(self):
        s=PAGE.read_text()
        for k in ("cellular-reconnect","cellular-switch-sim","cellular-internet-status",
                  "Internet", "signal-bars","normalizeOperator","api.cellularStatus",
                  "api.cellularAction('reconnect')","api.cellularAction('switchSim'"):
            self.assertIn(k,s)

    def test_no_automatic_storage_rpc(self):
        s=PAGE.read_text()
        click=s.index("smsCountButton?.addEventListener('click'")
        call=s.index("api.call('veci.cellular', 'messagingStorage'")
        self.assertLess(click,call)
        self.assertIn("output.textContent",s)
        self.assertNotIn("output.innerHTML",s)

if __name__=="__main__":
    unittest.main()
