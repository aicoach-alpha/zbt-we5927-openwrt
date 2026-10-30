"""Offline end-to-end release candidate gate with disposable fake build trees."""
import importlib.util
import json
import pathlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from contextlib import ExitStack

ROOT = pathlib.Path(__file__).resolve().parents[1]
FILE = ROOT / "scripts/finalize-veci-cafe-candidate.py"
spec = importlib.util.spec_from_file_location("cafe_finalizer", FILE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CandidateFinalizerTests(unittest.TestCase):
    def fixture(self, temp):
        base = pathlib.Path(temp)
        fw = base / "firmware"
        build = base / "openwrt"
        fw.mkdir()
        build.mkdir()
        (build / "rules.mk").write_text("test\n")
        (fw / "source").mkdir()
        (fw / "scripts").mkdir()
        (fw / "source/veci.commit").write_text("c" * 40 + "\n")
        (build / "package/veci-default-ui/files/etc").mkdir(parents=True)
        (build / "package/veci-default-ui/files/etc/veci-release.json").write_text(json.dumps(
            {"build_id": "f" * 40, "veci_commit": "c" * 40,
             "openwrt_commit": module.PINNED_OPENWRT, "edition": "general"}
        ))
        target = build / "bin/targets/ramips/mt76x8"
        target.mkdir(parents=True)
        image = target / "openwrt-zbt-we5927-sysupgrade.bin"
        image.write_bytes(b"A" * 128)
        manifest = target / "openwrt-zbt-we5927.manifest"
        manifest.write_text("veci-app-guest - 1\n")
        (build / "staging_dir/host/bin").mkdir(parents=True)
        tool = build / "staging_dir/host/bin/fwtool"
        tool.write_text("#!/bin/sh\nexit 0\n")
        tool.chmod(0o755)
        script = fw / "scripts/verify-veci-general-cafe-image.sh"
        script.write_text("#!/bin/sh\necho 'FLASH_DECISION=NO_GO_UNTIL_HARDWARE_RECOVERY_AND_UAT'\n")
        return fw, build, image, manifest

    def setup_mock(self):
        real_run = subprocess.run
        real_check = subprocess.check_output
        def command(args, **kwargs):
            if args[0] == "git" and args[-2:] == ["rev-parse", "HEAD"]:
                return ("a" * 40 if "firmware" in str(args[2])
                        else module.PINNED_OPENWRT)
            if args[0] == "git" and args[-2:] == ["show", "f" * 40 + ":source/veci.commit"]:
                return "c" * 40 + "\n"
            return real_check(args, **kwargs)
        def run(args, **kwargs):
            if args[0] == "git" and args[-2:] == ["cat-file", "-e"]:
                raise AssertionError("Unexpected git")
            if args[0] == "git" and args[-3:] == ["cat-file", "-e", "f" * 40 + "^{commit}"]:
                return subprocess.CompletedProcess(args, 0, "", "")
            if args[0] == "git" and len(args) >= 6 and args[3:5] == ["merge-base", "--is-ancestor"]:
                return subprocess.CompletedProcess(args, 0, "", "")
            return real_run(args, **kwargs)
        stack = ExitStack()
        stack.enter_context(patch.object(module.subprocess, "check_output", side_effect=command))
        stack.enter_context(patch.object(module.subprocess, "run", side_effect=run))
        stack.enter_context(patch.object(module, "verify_embedded_rootfs", return_value=True))
        return stack

    def test_missing_build_fails_without_creating_output(self):
        with tempfile.TemporaryDirectory() as d, self.setup_mock():
            fw, build, image, manifest = self.fixture(d)
            image.unlink()
            out = pathlib.Path("/mnt/data/andre-maintenance-archives") / (
                "veci-unit-not-created-" + pathlib.Path(d).name)
            with self.assertRaisesRegex(ValueError, "Expected exactly one"):
                module.finalize(fw, build, out)
            self.assertFalse(out.exists())

    def test_stale_build_metadata_fails(self):
        with tempfile.TemporaryDirectory() as d, self.setup_mock():
            fw, build, image, manifest = self.fixture(d)
            metadata = build / "package/veci-default-ui/files/etc/veci-release.json"
            stale = json.loads(metadata.read_text())
            stale["build_id"] = "0" * 40
            metadata.write_text(json.dumps(stale))
            with self.assertRaises(subprocess.CalledProcessError):
                module.finalize(fw, build, "/mnt/data/andre-maintenance-archives/veci-stale-test")

    def test_missing_fwtool_fails(self):
        with tempfile.TemporaryDirectory() as d, self.setup_mock():
            fw, build, image, manifest = self.fixture(d)
            (build / "staging_dir/host/bin/fwtool").unlink()
            with self.assertRaisesRegex(ValueError, "fwtool missing"):
                module.finalize(fw, build, "/mnt/data/andre-maintenance-archives/veci-fwtool-test")

    def test_unapproved_external_output_only(self):
        with tempfile.TemporaryDirectory() as d, self.setup_mock():
            fw, build, *_ = self.fixture(d)
            with self.assertRaisesRegex(ValueError, "external maintenance archive"):
                module.finalize(fw, build, pathlib.Path(d) / "candidate")
            with self.assertRaisesRegex(ValueError, "already exists"):
                module.finalize(fw, build, pathlib.Path(d))

    def test_verifier_failure_blocks(self):
        with tempfile.TemporaryDirectory() as d, self.setup_mock():
            fw, build, *_ = self.fixture(d)
            script = fw / "scripts/verify-veci-general-cafe-image.sh"
            script.write_text("#!/bin/sh\necho 'STOP bad image' >&2\nexit 7\n")
            with self.assertRaisesRegex(ValueError, "STOP bad image"):
                module.finalize(fw, build, "/mnt/data/andre-maintenance-archives/veci-invalid-test")

    def test_success_preserves_no_go_and_verifiable_sha(self):
        external = pathlib.Path("/mnt/data/andre-maintenance-archives")
        with tempfile.TemporaryDirectory(dir=external, prefix="veci-cafe-unit-") as d, self.setup_mock():
            fw, build, image, manifest = self.fixture(d)
            out = pathlib.Path(d) / "candidate"
            report = module.finalize(fw, build, out)
            self.assertTrue((out / "SHA256SUMS").is_file())
            self.assertTrue((out / image.name).is_file())
            self.assertEqual(report["source_commit"], "f" * 40)
            self.assertEqual(report["router_deployment"], "NOT_PERFORMED")
            self.assertTrue(report["flash_decision"].startswith("NO_GO"))
            verification = subprocess.run(
                ["sha256sum", "-c", "SHA256SUMS"], cwd=out,
                capture_output=True, text=True, timeout=5
            )
            self.assertEqual(verification.returncode, 0, verification.stderr)
            with self.assertRaisesRegex(ValueError, "already exists"):
                module.finalize(fw, build, out)

    def test_symlinked_parent_cannot_redirect_outside_archive(self):
        with tempfile.TemporaryDirectory() as d, self.setup_mock():
            fw, build, *_ = self.fixture(d)
            archive = pathlib.Path("/mnt/data/andre-maintenance-archives")
            link = archive / ("veci-gate-symlink-" + pathlib.Path(d).name)
            try:
                link.symlink_to(pathlib.Path(d), target_is_directory=True)
                with self.assertRaisesRegex(ValueError, "external maintenance archive"):
                    module.finalize(fw, build, link / "candidate")
                self.assertFalse((pathlib.Path(d) / "candidate").exists())
            finally:
                link.unlink(missing_ok=True)

    def test_squashfs_required_not_just_matching_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            file = pathlib.Path(d) / "firmware.bin"
            file.write_bytes(b"NOT_AN_EMBEDDED_SQUASHFS_IMAGE")
            with self.assertRaisesRegex(ValueError, "embedded SquashFS"):
                module.verify_embedded_rootfs(file, {"build_id":"f"*40})

    def test_embedded_filesystem_missing_required_file_is_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            image = pathlib.Path(d) / "firmware.bin"
            image.write_bytes(b"U-Boot" + b"hsqs" + b"A"*128)
            shim = pathlib.Path(d) / "unsquashfs"
            # A mock extractor that succeeds but does not extract a file must not pass.
            shim.write_text("#!/bin/sh\nexit 0\n")
            shim.chmod(0o755)
            with patch.object(module.shutil, "which", return_value=str(shim)):
                with self.assertRaisesRegex(ValueError, "Rootfs missing mandatory file"):
                    module.verify_embedded_rootfs(image, {"build_id":"f"*40})

    def test_no_router_or_publish_actions(self):
        content = FILE.read_text()
        self.assertIn("NO_GO_UNTIL_HARDWARE_RECOVERY_AND_UAT", content)
        self.assertIn("NOT_PERFORMED", content)
        for forbidden in ("sysupgrade -F", "sysupgrade -n", "gh release create", "apk add",
                          "ssh root@", "scp ", "uci set", "--privileged"):
            self.assertNotIn(forbidden, content)


if __name__ == "__main__":
    unittest.main()
