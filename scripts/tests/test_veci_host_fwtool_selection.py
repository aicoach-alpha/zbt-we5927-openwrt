#!/usr/bin/env python3
"""Enforce x86_64 native host fwtool selection on CI, never target MIPS binary."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/veci-select-host-fwtool.sh"


class HostFwtoolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "openwrt"
        (self.root / "include").mkdir(parents=True)
        (self.root / "include/toplevel.mk").write_text("dummy")
        (self.root / "staging_dir/host/bin").mkdir(parents=True)
        (self.root / "staging_dir/target-mipsel_24kc_musl/root-ramips/usr/bin").mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def run_gate(self):
        return subprocess.run(
            ["sh", str(SCRIPT), str(self.root)],
            capture_output=True, text=True, timeout=5, check=False,
        )

    def test_missing_host_binary_rejected_even_if_target_present(self):
        target = self.root / "staging_dir/target-mipsel_24kc_musl/root-ramips/usr/bin/fwtool"
        target.write_bytes(b"\x7fELF" + b"broken target")
        target.chmod(0o755)
        result = self.run_gate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("native_host_fwtool_missing", result.stderr)

    def test_native_host_binary_selected_not_target(self):
        true_bin = Path("/usr/bin/true")
        if not true_bin.is_file():
            self.skipTest("CI native binary unavailable")
        host = self.root / "staging_dir/host/bin/fwtool"
        shutil.copyfile(true_bin, host)
        host.chmod(0o755)
        result = self.run_gate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(host))

    def test_shell_script_not_accepted_as_native_fwtool(self):
        host = self.root / "staging_dir/host/bin/fwtool"
        host.write_text("#!/bin/sh\nexit 0\n")
        host.chmod(0o755)
        result = self.run_gate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fwtool_wrong_host_arch", result.stderr)

    def test_symlinked_host_tool_refused(self):
        host = self.root / "staging_dir/host/bin/fwtool"
        host.symlink_to("/usr/bin/true")
        result = self.run_gate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("native_host_fwtool_missing", result.stderr)


if __name__ == "__main__":
    unittest.main()
