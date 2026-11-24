"""Regression checks: exact source ID present, but never signed by CI."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/veci_release_manifest.py"
spec = importlib.util.spec_from_file_location("veci_release_manifest", SCRIPT)
manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest)


class ReleaseManifestTests(unittest.TestCase):
    def test_unverified_source_identity_is_not_a_release_approval(self):
        result = manifest.create_manifest("a" * 40, "b" * 40)
        self.assertEqual(result["build_id"], "a" * 40)
        self.assertEqual(result["target"], "ramips/mt76x8")
        self.assertEqual(result["board"], "zbtlink,zbt-we5927")
        self.assertEqual(result["image_signature"], "not_verified")
        self.assertEqual(result["channel"], "development")
        self.assertNotIn("flash_permission", result)

    def test_bad_sha_refused(self):
        for value in ("", "A" * 40, "../", "a" * 39, "a" * 41):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    manifest.create_manifest(value, "b" * 40)

    def test_real_checkout_embeds_exact_git_head(self):
        with tempfile.TemporaryDirectory() as root:
            out = Path(root) / "etc/veci-release.json"
            proc = subprocess.run(["python3", str(SCRIPT), "--repo", str(ROOT),
                                   "--out", str(out)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                           text=True).strip()
            contents = json.loads(out.read_text())
            self.assertEqual(contents["build_id"], head)

    def test_wrong_head_fails_without_creating_manifest(self):
        with tempfile.TemporaryDirectory() as root:
            out = Path(root) / "release.json"
            proc = subprocess.run(["python3", str(SCRIPT), "--repo", str(ROOT),
                                   "--out", str(out), "--expected-head", "f" * 40],
                                  capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)
            self.assertFalse(out.exists())

    def test_source_stager_and_package_install_release_metadata(self):
        stage = (ROOT / "scripts/stage-veci-reliability-rc.sh").read_text()
        pkg = (ROOT / "source/veci-app-catalog-we5927/Makefile").read_text()
        self.assertIn('scripts/veci_release_manifest.py', stage)
        self.assertIn('veci-app-catalog-we5927/files/etc/veci-release.json', stage)
        self.assertIn('$(1)/etc/veci-release.json', pkg)


if __name__ == "__main__":
    unittest.main()
