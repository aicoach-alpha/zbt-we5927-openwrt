"""Non-live regression of J9B mandatory fail-closed semantics."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
script=Path(__file__).resolve().parents[1]/"scripts/j9b_signed_feed_audit.py"
sys.path.insert(0,str(script.parent))
spec=importlib.util.spec_from_file_location("j9b",script)
m=importlib.util.module_from_spec(spec)
sys.modules["j9b"]=m
spec.loader.exec_module(m)
class J9BTests(unittest.TestCase):
    def test_no_results_not_pass(self):
        self.assertEqual(m.check_group([]),"NOT_TESTED")
    def test_partial_signature_fails(self):
        self.assertEqual(m.check_group([{"ok":True},{"ok":False}]),"BLOCKED")
    def test_all_signatures_pass(self):
        self.assertEqual(m.check_group([{"ok":True},{"ok":True}]),"PASS")
    def test_non_squashfs_fails(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"firmware.bin";p.write_bytes(b"no image")
            with self.assertRaises(ValueError):m.squashfs_offset(p)
    def test_ambiguous_squashfs_fails(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"firmware.bin";p.write_bytes(b"hsqs hello hsqs")
            with self.assertRaises(ValueError):m.squashfs_offset(p)
    def test_squashfs_offset(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"firmware.bin";p.write_bytes(b"0"*16+b"hsqs"+b"0"*10)
            self.assertEqual(m.squashfs_offset(p),16)
    def test_never_bypass_signatures_or_install(self):
        source=script.read_text()
        self.assertNotIn('"--allow-untrusted"',source)
        self.assertIn('"--simulate"',source)
        self.assertIn('"--no-network"',source)
        self.assertIn('"release_decision":"NO_GO"',source)
