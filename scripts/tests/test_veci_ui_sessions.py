import json
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ROOT / "rebuild/veci-v2/packages"


class UiSessions(unittest.TestCase):
    def test_login_permissions_and_logout(self):
        subprocess.run(["node", str(ROOT / "scripts/tests/fixtures/veci_ui_sessions.js"),
                        str(PACKAGES / "veci-v2-ui/files/www/veci2/app.js")],
                       check=True, timeout=10)

    def test_runtime_read_role_grants_only_self_logout_and_diagnostics(self):
        acl = json.loads((PACKAGES / "veci-v2-runtime/veci2-status-acl.json").read_text())
        runtime = acl["veci-v2-runtime"]
        self.assertEqual(runtime["read"]["ubus"]["session"], ["destroy"])
        self.assertEqual(runtime["write"]["ubus"], {})
        self.assertNotIn("unauthenticated", acl)
