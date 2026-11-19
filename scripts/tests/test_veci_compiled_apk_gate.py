"""Lab gate must reject a previous release even if its file is present."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CI = Path(__file__).resolve().parents[2] / "rebuild/veci-v2/ci/check-compiled-apks.py"


class CompiledApkGateTests(unittest.TestCase):
    def test_exact_files_from_package_recipes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for recipe in (CI.parents[1] / "packages").glob("*/Makefile"):
                fields = dict(line.split(":=", 1) for line in recipe.read_text().splitlines()
                              if line.startswith(("PKG_NAME:=", "PKG_VERSION:=", "PKG_RELEASE:=")))
                path = root / "{PKG_NAME}-{PKG_VERSION}-r{PKG_RELEASE}.apk".format(**fields)
                path.write_bytes(b"fixture")
            def run_gate():
                return subprocess.run([sys.executable, str(CI), str(root)], capture_output=True, text=True)
            self.assertEqual(run_gate().returncode, 0)
            runtime, = root.glob("veci-v2-runtime-*.apk")
            runtime.rename(root / "veci-v2-runtime-0.1-r0.apk")
            self.assertIn(runtime.name, run_gate().stderr)
            runtime.touch()
            self.assertNotEqual(run_gate().returncode, 0)
