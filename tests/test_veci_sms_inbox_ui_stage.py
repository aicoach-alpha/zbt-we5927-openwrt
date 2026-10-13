"""Predeployment-only UI: append-only to exact live v1.2, no auto SMS list."""
import hashlib
from pathlib import Path
import re
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=ROOT/"scripts/veci-sms-inbox-ui-staged-20261013/cellular.js"
LIVE_V12_SHA="2deb013e6ccf433b9c3abc3d7f02aafb33739dd1b5b5f222d4de501865314d40"
V12_NOTE="SMS Inbox is not enabled yet. Listing actual messages can mark unread SMS as read. This button reads storage totals only, never message contents or OTP."
V13_NOTE="This button checks storage totals only, never SMS content or OTP. SMS Inbox listing, if separately enabled, requires explicit administrator consent in the panel below."


class SmsIndexUI(unittest.TestCase):
    def setUp(self):
        self.text=UI.read_text()

    def test_node_syntax(self):
        x=subprocess.run(["node","--check",str(UI)],capture_output=True,text=True)
        self.assertEqual(x.returncode,0,x.stderr)

    def test_removing_only_index_panel_and_handler_recovers_live_v12_exactly(self):
        s=self.text
        panel=s.index('\t\t\t<section class="panel" aria-labelledby="cellular-sms-index-title">')
        end=s.index('\t\t\t<div class="notice-card">',panel)
        s=s[:panel]+s[end:]
        handler=s.index('\t\t// Sensitive operation: never fetch on navigation')
        end=s.index("\t\tconst reconnect = root.querySelector('#cellular-reconnect');",handler)
        s=s[:handler]+s[end:]
        self.assertIn(V13_NOTE,s)
        s=s.replace(V13_NOTE,V12_NOTE)
        self.assertEqual(hashlib.sha256(s.encode()).hexdigest(),LIVE_V12_SHA)

    def test_requires_checkbox_and_second_confirmation(self):
        s=self.text
        self.assertIn('id="cellular-sms-index-ack" type="checkbox"',s)
        self.assertIn('id="cellular-sms-index-open" type="button" disabled',s)
        self.assertIn("if (!indexAck?.checked || !indexButton || !indexOutput) return",s)
        self.assertIn("indexAck.checked = false",s)
        self.assertIn("const approved = await confirm(",s)
        self.assertIn("if (!approved) return",s)
        self.assertLess(s.index("if (!approved) return"),s.index("api.call('veci.sms'"))

    def test_exact_backend_contract_and_one_shot(self):
        s=self.text
        self.assertIn("api.call('veci.sms', 'listIndex'",s)
        self.assertIn("scope: 'metadata_only'",s)
        self.assertIn("ack_unread_status: 'I_ACCEPT_UNREAD_TO_READ'",s)
        self.assertIn("indexButton.disabled = true",s)
        self.assertIn("listIndex",s)
        self.assertNotIn("setInterval",s)
        self.assertNotIn("localStorage.setItem",s)
        self.assertNotIn("setTimeout(() => api.call('veci.sms'",s)

    def test_strict_bounded_metadata_and_no_html_from_modem(self):
        s=self.text
        self.assertIn("result.count <= 16",s)
        self.assertIn("row.index <= 65535",s)
        self.assertIn("row.status <= 4",s)
        self.assertIn("row.tpdu_octets <= 240",s)
        self.assertIn("new Set(rows.map(row => row.index)).size === rows.length",s)
        self.assertIn("document.createElement('li')",s)
        self.assertIn("indexOutput.replaceChildren(fragment)",s)
        self.assertNotIn("indexOutput.innerHTML",s)
        self.assertNotIn("rawPdu",s)
        self.assertNotIn("readSms",s)
        self.assertNotIn("sendSms",s)

    def test_storage_v12_remains_separate_and_privacy_preserving(self):
        s=self.text
        self.assertIn("api.call('veci.cellular', 'messagingStorage'",s)
        self.assertIn("read_only_at_cpms",s)
        self.assertIn("Check stored SMS count",s)
        self.assertIn("Number.isSafeInteger(result.used)",s)
        self.assertIn("smsCountButton?.addEventListener('click'",s)

    def test_legacy_cellular_controls_preserved(self):
        s=self.text
        for text in ("cellular-reconnect","cellular-switch-sim","cellular-internet-status",
                     "signal-bars","normalizeOperator","api.cellularStatus()",
                     "api.cellularAction('reconnect')","api.cellularAction('switchSim'"):
            self.assertIn(text,s)
        self.assertNotIn("AT+CMGL=4",s)
        self.assertNotIn("AT+CMGR=",s)
        self.assertNotIn("AT+CUSD=",s)

    def test_optional_package_not_firmware_live_or_auto_installed(self):
        mk=(ROOT/"source/veci-sms-inbox-we5927/Makefile").read_text()
        self.assertIn("PKG_NAME:=veci-sms-inbox-we5927",mk)
        sources=(ROOT/"scripts/prepare-veci.sh").read_text()
        self.assertNotIn("veci-sms-inbox-we5927",sources)
        self.assertNotIn("/etc/init.d/rpcd restart",mk)

if __name__=="__main__":
    unittest.main()
