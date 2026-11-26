"""All native JS sources must initialize with REAL index.html IDs, not ghost nodes."""
from pathlib import Path
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[2]
UI=ROOT/"rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2"
JSH=ROOT/"scripts/tests/fixtures/veci_v2_all_native_js_bootstrap.js"
class NativeGuiBootstrap(unittest.TestCase):
 def test_actual_script_order_loads_without_missing_dom_controls(self):
  p=subprocess.run(["node",str(JSH),str(UI/"index.html")],
                   capture_output=True,text=True,timeout=12)
  self.assertEqual(p.returncode,0,p.stdout+"\n"+p.stderr)
  self.assertIn("MISSING_STATIC_DOM_IDS []",p.stdout)
  self.assertIn("SCRIPTS_BOOTSTRAPPED",p.stdout)
if __name__=="__main__":unittest.main()
