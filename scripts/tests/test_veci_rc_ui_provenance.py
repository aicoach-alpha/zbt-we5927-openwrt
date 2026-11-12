import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "veci-rc-ui-provenance.py"
spec = importlib.util.spec_from_file_location("veci_ui", SCRIPT)
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)


class VeCiProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "veci"
        (self.root / "js").mkdir(parents=True)
        (self.root / "index.html").write_text("<h1>VeCI</h1>")
        (self.root / "js/app.js").write_text("export const app = true;")

    def tearDown(self):
        self.tmp.cleanup()

    def test_exactly_same_ui(self):
        a = ui.inventory(self.root)
        b = ui.inventory(self.root)
        self.assertTrue(ui.compare(a, b)["same_source"])
        self.assertFalse(ui.compare(a, b)["production_flash_authorized"])

    def test_changed_controller_detected(self):
        a = ui.inventory(self.root)
        (self.root / "js/app.js").write_text("export const app = false;")
        x = ui.compare(a, ui.inventory(self.root))
        self.assertEqual(x["changed"], ["js/app.js"])
        self.assertFalse(x["same_source"])

    def test_added_file_detected(self):
        a = ui.inventory(self.root)
        (self.root / "js/extra.js").write_text("export default 1")
        self.assertEqual(ui.compare(a, ui.inventory(self.root))["unapproved_new"],
                         ["js/extra.js"])

    def test_missing_file_detected(self):
        (self.root / "js/foo.js").write_text("foo")
        a = ui.inventory(self.root)
        (self.root / "js/foo.js").unlink()
        self.assertEqual(ui.compare(a, ui.inventory(self.root))["missing"], ["js/foo.js"])

    def test_symlink_inside_ui_rejected(self):
        link = self.root / "js/linked.js"
        link.symlink_to(self.root / "js/app.js")
        with self.assertRaisesRegex(ValueError, "symlink"):
            ui.inventory(self.root)

    def test_missing_entrypoints_rejected(self):
        (self.root / "js/app.js").unlink()
        with self.assertRaisesRegex(ValueError, "entrypoints"):
            ui.inventory(self.root)

    def test_private_file_type_rejected(self):
        (self.root / "secrets.pem").write_text("-----BEGIN PRIVATE KEY-----")
        with self.assertRaisesRegex(ValueError, "unknown_ui_asset"):
            ui.inventory(self.root)

    def test_invalid_manifest_rejected(self):
        good = ui.inventory(self.root)
        bad = {"schema_version": 1, "files": {"js/app.js": "not_a_sha"}}
        with self.assertRaisesRegex(ValueError, "invalid_manifest"):
            ui.compare(bad, good)


if __name__ == "__main__":
    unittest.main()
