"""The next VeCI firmware cannot silently lose fixes or claim fake PASS."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]
BUG=ROOT/"rebuild/veci-v2/ci/bug-regression-gate.py"
COMPLETE=ROOT/"rebuild/veci-v2/ci/source-completion-gate.py"
ROM=ROOT/"rebuild/veci-v2/ci/check-all-core-rom.py"
PKG=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime"
TESTS=ROOT/"scripts/tests"

def load(source,label):
 spec=importlib.util.spec_from_file_location(label,source)
 module=importlib.util.module_from_spec(spec)
 spec.loader.exec_module(module)
 return module

class FirmwareDefectGate(unittest.TestCase):
 def test_catalog_is_real_exact_module_coverage(self):
  audit=load(BUG,"bugaudit").audit()
  self.assertTrue(audit["ok"],audit["errors"])
  self.assertEqual(audit["required_active_modules"],39)
  self.assertEqual(audit["covered_active_modules"],39)
  self.assertGreaterEqual(audit["registered_known_cases"],25)
  reg=json.loads((ROOT/"rebuild/veci-v2/contracts/veci-v2-bug-registry-20261126.json").read_text())
  ids=[v["id"] for v in reg["bugs"]]
  self.assertEqual(len(ids),len(set(ids)))
  self.assertTrue(all(x["regression_test_files"] for x in reg["bugs"]))
  self.assertFalse(any("lte_ussd" in x["affected_modules"] for x in reg["bugs"]))
 def test_each_registered_bug_test_has_executable_test_methods(self):
  reg=json.loads((ROOT/"rebuild/veci-v2/contracts/veci-v2-bug-registry-20261126.json").read_text())
  for case in reg["bugs"]:
   for name in case["regression_test_files"]:
    f=TESTS/name
    self.assertTrue(f.is_file(),(case["id"],name))
    self.assertIn("def test_",f.read_text(),(case["id"],name))
 def test_both_source_and_release_remain_blocked(self):
  mod=load(BUG,"bugsource")
  x=mod.audit()
  self.assertEqual(x["modules_requiring_hardware_uat"],39)
  self.assertFalse(x["release_permitted"])
  for gate in ("register","source","release"):
   run=subprocess.run(["python3",str(BUG),"--gate",gate],capture_output=True,text=True,timeout=6)
   expected=0 if gate=="register" or (gate=="source" and x["source_build_permitted"]) else 3
   self.assertEqual(run.returncode,expected,run.stderr)
   self.assertTrue(json.loads(run.stdout)["ok"])
 def test_critical_source_defect_blocks_canonical_build(self):
  b=load(COMPLETE,"canonical_source_gate")
  contract=json.loads((ROOT/"rebuild/veci-v2/contracts/veci-v2-rebuild-contract.json").read_text())
  evidence=json.loads((ROOT/"rebuild/veci-v2/contracts/owner-final-source-evidence.json").read_text())
  blockers=b.audit(contract,evidence)
  registry=json.loads((ROOT/"rebuild/veci-v2/contracts/veci-v2-bug-registry-20261126.json").read_text())
  for item in registry["bugs"]:
   if item["source_state"]=="source_open":
    self.assertIn("known_source_bug_unresolved:"+item["id"],blockers)
  report=load(BUG,"latest_defects").audit()
  self.assertEqual(report["source_build_permitted"],not bool(
    report["errors"] or report["known_source_open"] or report["historical_receipt_hash_mismatches"]))
  self.assertFalse(contract["flash_authorized"])
 def test_no_network_reload_wifi_or_duplicate_modem_manager(self):
  helper=(PKG/"veci2-wifi-activate").read_text()
  # Comments are policy but only executable lines define actual safety.
  code="\n".join(x for x in helper.splitlines() if not x.lstrip().startswith("#"))
  for unsafe in ("call network reload","wifi reload","wifi up","ifup lte",
                 "ifdown lte","sysupgrade","AT+CFUN"):
   self.assertNotIn(unsafe,code)
  import re
  self.assertNotRegex(code,re.compile(r"(?m)^\s*(?:reboot|wifi|sysupgrade|ifup|ifdown)\b"))
  self.assertIn("record prepared_next_reboot",helper)
  self.assertIn("uci -q commit wireless",helper)
  self.assertIn("config_restore_unverified",helper)
  gui=(ROOT/"rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2/app.js").read_text()
  self.assertIn("PREPARE_WPA2_AP_NEXT_BOOT",gui)
  self.assertIn("reboot manual",gui.lower())
 def test_final_rom_cannot_pass_without_new_helper(self):
  script=ROM.read_text()
  self.assertIn('(RTL+"veci2-wifi-activate","usr/libexec/veci2-wifi-activate")',script)
  package=(PKG/"Makefile").read_text()
  self.assertIn('$(INSTALL_BIN) ./veci2-wifi-activate $(1)/usr/libexec/veci2-wifi-activate',package)
 def test_ci_runs_catalog_and_all_native_tests(self):
  ci=(ROOT/".github/workflows/veci-v2-rebuild-source.yml").read_text()
  self.assertIn("--gate register",ci)
  self.assertIn("test_*.py' -v",ci)
  lab=(ROOT/".github/workflows/veci-v2-lab-image.yml").read_text()
  self.assertLess(lab.index("source-completion-gate.py"),
                  lab.index("Install OpenWrt host dependencies"))
if __name__=="__main__":unittest.main()
