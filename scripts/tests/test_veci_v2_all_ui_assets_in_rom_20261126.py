"""Exact rebuilt ROM includes all referenced native JS and CSS assets."""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"rebuild/veci-v2/ci/check-all-core-rom.py"
spec=importlib.util.spec_from_file_location("veci_asset_rom",SCRIPT)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class AllUiAssetsRomGate(unittest.TestCase):
 def test_all_referenced_native_files_are_mandatory(self):
  ui=mod.FEATURES["ui_four_group_navigation"]
  self.assertGreaterEqual(len(mod.REFERENCED_ASSETS),23)
  self.assertIn(("rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2/veci-design.css",
                 "www/veci2/veci-design.css"),ui)
  self.assertIn(("rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2/services.js",
                 "www/veci2/services.js"),ui)
  self.assertEqual(len(mod.REFERENCED_ASSETS),len(set(mod.REFERENCED_ASSETS)))
 def test_missing_design_stylesheet_in_rom_is_hard_fail(self):
  with tempfile.TemporaryDirectory() as folder:
   rom=Path(folder)
   for entries in mod.FEATURES.values():
    for original,relative in entries:
     dst=rom/relative;dst.parent.mkdir(parents=True,exist_ok=True)
     shutil.copyfile(ROOT/original,dst)
   self.assertEqual(mod.check(rom),[])
   (rom/"www/veci2/veci-design.css").unlink()
   problems=mod.check(rom)
   self.assertIn("ROM_MISSING_OR_WRONG_SIZE:ui_four_group_navigation:www/veci2/veci-design.css",problems)

if __name__=="__main__":unittest.main()
