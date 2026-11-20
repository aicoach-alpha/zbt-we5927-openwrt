"""Source-reuse wiring checks only; never claims hardware UAT/feature parity."""
import json
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ROOT / "rebuild/veci-v2/packages"
RUNTIME = PACKAGES / "veci-v2-runtime"
UI = PACKAGES / "veci-v2-ui"
HTML = (UI / "files/www/veci2/index.html").read_text()
APP = (UI / "files/www/veci2/app.js").read_text()
RUNTIME_MAKEFILE = (RUNTIME / "Makefile").read_text()
UI_MAKEFILE = (UI / "Makefile").read_text()


class ExistingSourceReuse(unittest.TestCase):
    def test_all_27_requirements_provenance_documented_without_false_pass(self):
        doc = (ROOT / "docs/SOURCE_REUSE_27_MODULES.md").read_text()
        contract = json.loads((ROOT / "rebuild/veci-v2/contracts/veci-v2-rebuild-contract.json").read_text())
        required = {entry["id"] for entry in contract["required_core"] if entry["v2_state"] == "not_ported_to_v2"}
        entries = re.findall(r"^\| ([a-z][a-z0-9_]*) \|", doc, re.M)
        self.assertEqual(len(entries), 27)
        self.assertEqual(set(entries), required)
        self.assertIn("64900e756efa667774214f9c6b17c113222e01f7", doc)
        self.assertIn("DO NOT", doc.upper() if "DO NOT" in doc.upper() else doc.upper().replace("JANGAN", "DO NOT"))
        self.assertNotIn("27/27 PASS", doc)

    def test_imported_veci_rpc_scripts_and_scoped_acls(self):
        for name, methods in [
            ("interfaces", ["status", "save"]),
            ("routes", ["status", "save", "remove"]),
            ("access", ["status", "setIdle", "requireHttps"]),
        ]:
            with self.subTest(provider=name):
                script = RUNTIME / ("veci2-" + name)
                acl = RUNTIME / ("veci2-" + name + "-acl.json")
                self.assertTrue(script.is_file() and acl.is_file())
                subprocess.run(["sh", "-n", str(script)], check=True, capture_output=True)
                records = json.loads(acl.read_text())
                self.assertIn("veci.v2." + name, json.dumps(records))
                for method in methods:
                    self.assertIn(method, script.read_text())
                self.assertIn("veci.v2." + name, RUNTIME_MAKEFILE)
                self.assertIn("veci2-" + name + "-acl.json", RUNTIME_MAKEFILE)

    def test_ui_wiring_and_deferred_order(self):
        index = HTML.index('<script src="/veci2/app.js" defer></script>')
        for name in ("interfaces", "routes", "access"):
            with self.subTest(name=name):
                self.assertGreater(HTML.index(f'<script src="/veci2/{name}.js" defer></script>'), index)
                src = UI / f"files/www/veci2/{name}.js"
                subprocess.run(["node", "--check", str(src)], check=True, capture_output=True)
                self.assertIn(f"{name}.js", UI_MAKEFILE)
                self.assertIn(f"globalThis.Veci{name.capitalize()}?.reset()", APP)

    def test_nonduplicated_native_services(self):
        self.assertEqual(HTML.count('id="interface-form"'), 1)
        self.assertEqual(HTML.count('id="route-form"'), 1)
        self.assertEqual(HTML.count('id="access-read"'), 1)
        for path in (RUNTIME / "veci2-interfaces", RUNTIME / "veci2-routes",
                     RUNTIME / "veci2-access"):
            text = path.read_text()
            self.assertIn("zbtlink,zbt-we5927", text)
            self.assertIn("flock", text)
            self.assertNotIn("AT+CFUN", text)
            self.assertNotIn("sysupgrade ", text)


if __name__ == "__main__":
    unittest.main()
