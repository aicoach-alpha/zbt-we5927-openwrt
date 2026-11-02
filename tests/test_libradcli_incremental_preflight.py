"""Offline tests for scoped non-idempotent radcli staging alias repair."""
import importlib.util
import ast
import pathlib
import subprocess
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
HELPER=ROOT/"scripts/prepare-libradcli-install-aliases.py"
WRAPPER=ROOT/"scripts/run-veci-general-cafe-container.sh"
spec=importlib.util.spec_from_file_location("libradcli_aliases", HELPER)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RadcliAliasTests(unittest.TestCase):
    def fixture(self, base):
        root=pathlib.Path(base)
        dest=root/module.ALIAS_DIR
        dest.mkdir(parents=True)
        (dest/"libradcli.so").write_text("test-only")
        for name in module.ALIASES:
            (dest/name).symlink_to("libradcli.so")
        (dest/"unrelated-state").write_text("keep")
        return root,dest

    def test_clear_exact_two_and_preserve_unrelated(self):
        with tempfile.TemporaryDirectory() as d:
            root,dest=self.fixture(d)
            self.assertEqual(set(module.clear_known_aliases(root)),set(module.ALIASES))
            for name in module.ALIASES:
                self.assertFalse((dest/name).exists())
                self.assertFalse((dest/name).is_symlink())
            self.assertEqual((dest/"unrelated-state").read_text(),"keep")
            self.assertTrue((dest/"libradcli.so").is_file())
            self.assertEqual(module.clear_known_aliases(root),[])

    def test_unexpected_symlink_target_blocks_without_partial_cleanup(self):
        with tempfile.TemporaryDirectory() as d:
            root,dest=self.fixture(d)
            (dest/module.ALIASES[1]).unlink()
            (dest/module.ALIASES[1]).symlink_to("../../outside")
            with self.assertRaisesRegex(ValueError,"unexpected radcli alias"):
                module.clear_known_aliases(root)
            self.assertTrue((dest/module.ALIASES[0]).is_symlink())

    def test_regular_file_blocks_without_partial_cleanup(self):
        with tempfile.TemporaryDirectory() as d:
            root,dest=self.fixture(d)
            (dest/module.ALIASES[1]).unlink()
            (dest/module.ALIASES[1]).write_text("not-a-symlink")
            with self.assertRaisesRegex(ValueError,"unexpected regular"):
                module.clear_known_aliases(root)
            self.assertTrue((dest/module.ALIASES[0]).is_symlink())

    def test_missing_target_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root,dest=self.fixture(d)
            (dest/"libradcli.so").unlink()
            with self.assertRaisesRegex(ValueError,"library target is missing"):
                module.clear_known_aliases(root)

    def test_unprepared_staging_is_noop(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(module.clear_known_aliases(d),[])

    def test_wrapper_uses_bounded_scoped_preflight_only_during_build(self):
        content=WRAPPER.read_text()
        self.assertIn('if [ "$mode" = build ]; then', content)
        self.assertIn('prepare-libradcli-install-aliases.py',content)
        self.assertIn('--cpus=1.5',content)
        self.assertIn('--memory=4g',content)
        self.assertIn('--cap-drop=ALL',content)
        self.assertNotIn('sysupgrade -F',content)
        self.assertEqual(subprocess.run(['sh','-n',str(WRAPPER)]).returncode,0)
        self.assertIsNotNone(ast.parse(HELPER.read_text()))

if __name__=="__main__":
    unittest.main()
