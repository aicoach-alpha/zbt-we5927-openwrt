"""Scope-specific source checks; not hardware UAT or release clearance."""
import hashlib
import json
import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
TRACK='system'
RECORD=json.loads((ROOT / ("docs/PARALLEL_REUSE_" + TRACK.upper() + "_20261120.json")).read_text())
RT=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime"
UI=ROOT/"rebuild/veci-v2/packages/veci-v2-ui"
HTML=(UI/"files/www/veci2/index.html").read_text()
APP=(UI/"files/www/veci2/app.js").read_text()
RMAKE=(RT/"Makefile").read_text()
UMAKE=(UI/"Makefile").read_text()

class ScopeIntegration(unittest.TestCase):
    def test_original_sources_not_rewritten(self):
        self.assertFalse(RECORD["full_module_verified"])
        self.assertEqual(RECORD["hardware_uat"],"not_run")
        for item in RECORD["reused_byte_identical_sources"]:
            with self.subTest(path=item["path"]):
                digest=hashlib.sha256((ROOT/item["path"]).read_bytes()).hexdigest()
                if digest != item["sha256"]:
                    # Historical a66f7ec receipt remains immutable; any newer
                    # revision must match its exact reviewed git commit.
                    self.assertEqual(digest,item.get("reviewed_successor_sha256"))
                    commit=item.get("reviewed_successor_commit")
                    self.assertEqual(commit,"04e8058")
                    committed=subprocess.check_output(
                        ["git","-C",str(ROOT),"show",commit+":"+item["path"]])
                    self.assertEqual(hashlib.sha256(committed).hexdigest(),digest)
                else:
                    self.assertEqual(digest,item["sha256"])
    def test_no_duplicate_ui_ids_and_scripts_load_after_main(self):
        import re
        ids=re.findall(r'\bid="([^"]+)"',HTML)
        self.assertEqual(len(ids),len(set(ids)),set(x for x in ids if ids.count(x)>1))
        app_at=HTML.index('/veci2/app.js"')
        for js in RECORD["reused_byte_identical_sources"]:
            if js["path"].endswith(".js"):
                self.assertGreater(HTML.index('/veci2/'+Path(js["path"]).name+'"'),app_at)
                self.assertIn(Path(js["path"]).name,UMAKE)
                subprocess.run(["node","--check",str(ROOT/js["path"])],check=True,capture_output=True,timeout=7)
    def test_provider_scripts_have_valid_syntax(self):
        for item in RECORD["reused_byte_identical_sources"]:
            p=ROOT/item["path"]
            if "veci2-" in p.name and not p.name.endswith((".json",".js",".awk")):
                subprocess.run(["sh","-n",str(p)],check=True,capture_output=True,timeout=7)
    def test_explicit_source_only_status(self):
        contract=json.loads((ROOT/"rebuild/veci-v2/contracts/veci-v2-rebuild-contract.json").read_text())
        self.assertFalse(contract["flash_authorized"])
        self.assertEqual(len(contract["required_core"]),39)

if __name__=="__main__": unittest.main()
