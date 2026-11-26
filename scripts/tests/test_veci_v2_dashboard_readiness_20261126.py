"""Native dashboard reports distinct, truthful service readiness."""
from pathlib import Path
import re
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[2]
UI=ROOT/"rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2"
class DashboardReadiness(unittest.TestCase):
 def test_lte_wifi_network_sms_are_separate_and_not_fake_pass(self):
  html=(UI/"index.html").read_text()
  js=(UI/"app.js").read_text()
  css=(UI/"veci-design.css").read_text()
  for label,key in (("Internet LTE","shell-lte-status"),
                    ("Wi-Fi utama","shell-wifi-status"),
                    ("Layanan jaringan","shell-router-status"),
                    ("SMS modem","shell-sms-status")):
   self.assertIn(label,html)
   self.assertEqual(html.count('id="'+key+'"'),1)
   self.assertIn(key,js)
  self.assertIn("async function refreshSmsReadiness()",js)
  self.assertIn("result.provider_registered === true",js)
  self.assertIn("result.modem_at_port_present === true",js)
  self.assertIn("result.config_present === true",js)
  self.assertIn("result.source !== 'live_read_only'",js)
  self.assertIn("kirim/terima belum diuji",js)
  self.assertNotIn("SMS terverifikasi",js)
  self.assertIn("grid-template-columns:repeat(4,minmax(0,1fr))",css)
  self.assertIn("@media(max-width:640px){.connectivity-summary{grid-template-columns:1fr}}",css)
  subprocess.run(["node","--check",str(UI/"app.js")],check=True,timeout=4)
 def test_full_gui_bootstrap_still_has_no_ghost_controls(self):
  runner=ROOT/"scripts/tests/fixtures/veci_v2_all_native_js_bootstrap.js"
  p=subprocess.run(["node",str(runner),str(UI/"index.html")],
                   capture_output=True,text=True,timeout=10)
  self.assertEqual(p.returncode,0,p.stderr+p.stdout)
  self.assertIn("MISSING_STATIC_DOM_IDS []",p.stdout)
  self.assertIn("MISSING_FORM_FIELDS []",p.stdout)
if __name__=="__main__":unittest.main()
