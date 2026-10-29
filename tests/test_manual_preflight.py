import csv
import pathlib
import unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
class OperatorKitTests(unittest.TestCase):
    def test_preflight_read_only_and_board_bound(self):
        text = (ROOT / "scripts/veci-router-preflight.ps1").read_text()
        self.assertIn("ubus call system board", text)
        self.assertIn("zbtlink,zbt-we5927", text)
        self.assertIn("ramips/mt76x8", text)
        self.assertIn("Get-FileHash", text)
        self.assertIn("BatchMode=no", text)
        self.assertIn("NumberOfPasswordPrompts=1", text)
        self.assertIn("StrictHostKeyChecking=ask", text)
        self.assertNotIn("sysupgrade -F", text)
        self.assertNotIn("ssh root@192.168.1.1", text)
    def test_http_fallback_not_forced_to_https(self):
        base = ROOT / 'source/veci-default-ui/files/etc/uci-defaults'
        for fname in ['97-veci-https-defaults','98-veci-default-ui']:
            text = (base / fname).read_text()
            self.assertNotIn('redirect_https=', text)
            self.assertNotIn("redirect_https='1'", text)
            self.assertNotIn('listen_http=0', text)
        doc = (ROOT / 'docs/VECI-MANUAL-DEPLOY-20261029.md').read_text()
        self.assertIn('Never disable HTTP', doc)
    def test_evidence_template_has_16_untested_cases(self):
        path = ROOT / 'docs/VECI-MANUAL-UAT-EVIDENCE.csv'
        with path.open(newline='') as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 16)
        self.assertEqual([row['Case ID'] for row in rows], ['U%02d' % n for n in range(1,17)])
        self.assertTrue(all(row['Status']=='NOT_TESTED' for row in rows))
        self.assertTrue(all(not row['Firmware image SHA256'] for row in rows))
    def test_doc_has_correct_approval_gates(self):
        text = (ROOT / "docs/VECI-MANUAL-DEPLOY-20261029.md").read_text()
        for term in ("FLASH NO_GO", "81853a6", "f1dc4d8", "2026-10-06", "U01–U16", "SOURCE_PASS", "HARDWARE_UAT_PASS"):
            self.assertIn(term, text)
if __name__ == "__main__":
    unittest.main()
