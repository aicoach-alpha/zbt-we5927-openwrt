"""Prevent all-features-complete claims when only native UI stubs ship."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "native_audit", ROOT / "scripts/audit_veci_firmware_features.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class NativeFeatureTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def put(self, path, content="present"):
        dest = self.root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)

    def test_empty_image_is_not_complete(self):
        out = module.inventory(self.root)
        self.assertEqual(out["static_feature_parity"], "FAIL")
        self.assertFalse(out["production_flash_permission"])
        self.assertIn("guest_portal_runtime", out["missing"])
        self.assertIn("operator_quota_backend", out["missing"])

    def test_catalog_does_not_substitute_for_voucher_or_guest_runtime(self):
        self.put("www/veci/js/pages/hotspot.js")
        self.put("usr/share/veci/apps/guest.json", "{}")
        self.put("usr/share/veci/apps/voucher.json", "{}")
        out = module.inventory(self.root)
        self.assertFalse(out["checks"]["guest_portal_runtime"])
        self.assertFalse(out["checks"]["voucher_runtime"])

    def test_native_entrypoint_cannot_redirect_to_luci(self):
        self.put("www/index.html", '<meta http-equiv="refresh" content="0; URL=cgi-bin/luci/">')
        self.assertFalse(module.inventory(self.root)["checks"]["veci_native_home"])
        self.put("www/index.html", '<meta http-equiv="refresh" content="0; url=/veci/">')
        self.assertTrue(module.inventory(self.root)["checks"]["veci_native_home"])

    def test_real_build_id_checks_board_and_sha(self):
        self.put("etc/veci-release.json", json.dumps({"board": "zbtlink,zbt-we5927",
                                                       "build_id": "a"*40}))
        self.assertTrue(module.inventory(self.root)["checks"]["release_identity"])
        self.put("etc/veci-release.json", '{"build_id":"invalid","board":"zbtlink,zbt-we5927"}')
        self.assertFalse(module.inventory(self.root)["checks"]["release_identity"])

    def test_build_profile_stages_true_veci_home_and_identity(self):
        stager = (ROOT / "scripts/stage-veci-reliability-rc.sh").read_text()
        self.assertIn('VECI_NATIVE_LANDING_AND_REAL_RELEASE_ID_STAGED=PASS', stager)
        self.assertIn('files/etc/veci-release.json', stager)
        self.assertIn('files/www/index.html', stager)
        landing = (ROOT / "source/veci-default-ui/files/www/index.html").read_text()
        self.assertIn('url=/veci/', landing)
        self.assertNotIn('URL=cgi-bin/luci/', landing)

    def test_native_js_cache_bust_and_build_marker(self):
        html = (ROOT / "source/veci-core/veci/index.html").read_text()
        app = (ROOT / "source/veci-core/veci/js/app.js").read_text()
        self.assertIn('app.js?v=162', html)
        self.assertIn('app.css?v=162', html)
        self.assertIn('id="topbar-build"', html)
        self.assertIn('/veci/build.json', app)
        self.assertIn('home.js?v=162', app)
        self.assertIn('cellular.js?v=162', app)

    def test_static_check_can_never_authorize_flash(self):
        self.assertFalse(module.inventory(self.root)["production_flash_permission"])

if __name__ == "__main__":
    unittest.main()
