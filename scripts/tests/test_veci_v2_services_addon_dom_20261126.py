"""Load actual native GUI services and add-on modules against the real IDs."""
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]
UI=ROOT/"rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2"
FIXTURE=ROOT/"scripts/tests/fixtures/veci_v2_services_addon_dom.js"

class ServicesAddonDom(unittest.TestCase):
 def test_both_existing_menus_have_single_live_handler_path(self):
  proc=subprocess.run(["node",str(FIXTURE),str(UI/"services.js"),str(UI/"addon-profiles.js")],
                      capture_output=True,text=True,timeout=8)
  self.assertEqual(proc.returncode,0,proc.stderr)
  self.assertIn("PASS: canonical startup and addon DOM",proc.stdout)
 def test_old_missing_addon_read_is_not_required(self):
  html=(UI/"index.html").read_text()
  self.assertNotIn('id="addon-read"',html)
  self.assertIn('id="startup-read"',html)
  self.assertIn('id="addon-profiles-read"',html)
  self.assertNotIn("getElementById('addon-read')",(UI/"services.js").read_text())
if __name__=="__main__":unittest.main()
