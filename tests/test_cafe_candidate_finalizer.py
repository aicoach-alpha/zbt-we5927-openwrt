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
        (fw / "docs").mkdir()
        (fw / "docs/WE5927-OPERATOR-MTD-EVIDENCE-20261030.json").write_text(
            (ROOT / "docs/WE5927-OPERATOR-MTD-EVIDENCE-20261030.json").read_text()
        )
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

    def setup_mock(self, head="f" * 40):
        real_run = subprocess.run
        real_check = subprocess.check_output
        def command(args, **kwargs):
            if args[0] == "git" and args[-2:] == ["rev-parse", "HEAD"]:
                return (head if "firmware" in str(args[2])
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

    def test_real_operator_mtd_evidence_matches_reported_hardware(self):
        with tempfile.TemporaryDirectory() as d:
            fw, build, image, _ = self.fixture(d)
            result = module.verify_hardware_attestation(fw, image)
            self.assertEqual(result["mtd_firmware_bytes"], 7995392)
            self.assertEqual(result["board"], "zbtlink,zbt-we5927")
            self.assertEqual(result["spare_partition_bytes"], 7995392 - 128)
            self.assertEqual(result["decision"], "CAPACITY_PASS_ONLY_FLASH_NO_GO")

    def test_firmware_image_exceeding_real_partition_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            fw, build, image, _ = self.fixture(d)
            with image.open("r+b") as file:
                file.truncate(7995393)
            with self.assertRaisesRegex(ValueError, "exceeds verified firmware partition"):
                module.verify_hardware_attestation(fw, image)

    def test_operator_mtd_evidence_cannot_be_missing_or_mutated(self):
        with tempfile.TemporaryDirectory() as d:
            fw, build, image, _ = self.fixture(d)
            evidence = fw / "docs/WE5927-OPERATOR-MTD-EVIDENCE-20261030.json"
            data = json.loads(evidence.read_text())
            data["partition_size_bytes"] = 16777216
            evidence.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "invalid or mismatched"):
                module.verify_hardware_attestation(fw, image)
            evidence.unlink()
            with self.assertRaisesRegex(ValueError, "Missing physical MTD"):
                module.verify_hardware_attestation(fw, image)

    def test_operator_mtd_json_type_and_report_name_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            fw, build, image, _ = self.fixture(d)
            evidence = fw / "docs/WE5927-OPERATOR-MTD-EVIDENCE-20261030.json"
            evidence.write_text("[]")
            with self.assertRaisesRegex(ValueError, "JSON object"):
                module.verify_hardware_attestation(fw, image)
            data = json.loads((ROOT / "docs/WE5927-OPERATOR-MTD-EVIDENCE-20261030.json").read_text())
            del data["operator_report_basename"]
            evidence.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "report reference"):
                module.verify_hardware_attestation(fw, image)
            data["operator_report_basename"] = "../secrets.txt"
            evidence.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "report reference"):
                module.verify_hardware_attestation(fw, image)

    def test_real_squashfs_extraction_and_embedded_release_fields(self):
        import shutil
        if not shutil.which("mksquashfs") or not shutil.which("unsquashfs"):
            self.skipTest("SquashFS host tools not installed")
        with tempfile.TemporaryDirectory() as d:
            work = pathlib.Path(d)
            tree = work / "root"
            needed = [
                "etc/veci-release.json",
                "usr/libexec/rpcd/veci",
                "usr/libexec/rpcd/veci.apps",
                "usr/libexec/rpcd/veci.app.guest",
                "usr/libexec/rpcd/veci.app.voucher",
                "www/veci/index.html",
                "usr/libexec/veci/guest-prerm",
                "usr/libexec/veci/voucher-prerm",
                "etc/apk/keys/openwrt-public.pem"
            ]
            metadata = {
                "build_id": "f" * 40,
                "veci_commit": "c" * 40,
                "openwrt_commit": module.PINNED_OPENWRT,
                "edition": "general"
            }
            for name in needed:
                file = tree / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(json.dumps(metadata) if name.endswith("veci-release.json")
                                else "UNIT_TEST_DATA_NOT_AN_APK_SIGNATURE")
            filesystem = work / "filesystem.squashfs"
            build = subprocess.run(
                ["mksquashfs", str(tree), str(filesystem),
                 "-noappend", "-no-progress", "-processors", "1"],
                capture_output=True, text=True, timeout=20
            )
            self.assertEqual(build.returncode, 0, build.stderr[-600:])
            image = work / "synthetic-sysupgrade.bin"
            image.write_bytes(b"SYNTHETIC_IMAGE_HEADER" + filesystem.read_bytes())
            self.assertTrue(module.verify_embedded_rootfs(image, metadata))
            self.assertTrue(module.verify_embedded_rootfs(image, metadata, require_prerm_hooks=False))
            (tree / "usr/libexec/veci/guest-prerm").unlink()
            oldfs = work / "missing-hook.squashfs"
            result = subprocess.run(
                ["mksquashfs", str(tree), str(oldfs),
                 "-noappend", "-no-progress", "-processors", "1"],
                capture_output=True, text=True, timeout=20
            )
            self.assertEqual(result.returncode, 0, result.stderr[-400:])
            oldimage = work / "missing-hook-sysupgrade.bin"
            oldimage.write_bytes(b"SYNTHETIC_IMAGE_HEADER" + oldfs.read_bytes())
            with self.assertRaisesRegex(ValueError, "Rootfs missing mandatory file usr/libexec/veci/guest-prerm"):
                module.verify_embedded_rootfs(oldimage, metadata)
            self.assertTrue(module.verify_embedded_rootfs(oldimage, metadata, require_prerm_hooks=False))
            metadata["edition"] = "indonesia"
            with self.assertRaisesRegex(ValueError, "Embedded rootfs release metadata mismatch"):
                module.verify_embedded_rootfs(image, metadata)

    def test_stale_build_is_hard_refused_for_production(self):
        with tempfile.TemporaryDirectory() as d, self.setup_mock(head="a" * 40):
            fw, build, image, _ = self.fixture(d)
            target = pathlib.Path("/mnt/data/andre-maintenance-archives") / ("veci-stale-" + pathlib.Path(d).name)
            with self.assertRaisesRegex(ValueError, "STALE_BUILD_REQUIRES_REBUILD"):
                module.finalize(fw, build, target)
            self.assertFalse(target.exists())

    def test_explicit_historical_audit_retains_no_go(self):
        external = pathlib.Path("/mnt/data/andre-maintenance-archives")
        with tempfile.TemporaryDirectory(dir=external, prefix="veci-history-") as d, self.setup_mock(head="a" * 40):
            fw, build, image, _ = self.fixture(d)
            report = module.finalize(fw, build, pathlib.Path(d)/"forensic",
                                     allow_stale_audit=True)
            self.assertEqual(report["source_freshness"], "STALE")
            self.assertIn("HISTORICAL_AUDIT", report["status"])
            self.assertEqual(report["flash_decision"], "NO_GO_STALE_BUILD_REQUIRES_REBUILD")
            self.assertEqual(report["router_deployment"], "NOT_PERFORMED")

    def test_fresh_release_still_requires_hardware_uat(self):
        external = pathlib.Path("/mnt/data/andre-maintenance-archives")
        with tempfile.TemporaryDirectory(dir=external, prefix="veci-fresh-") as d, self.setup_mock():
            fw, build, image, _ = self.fixture(d)
            report = module.finalize(fw, build, pathlib.Path(d)/"fresh")
            self.assertEqual(report["source_freshness"], "CURRENT")
            self.assertEqual(report["current_repo_commit"], report["source_commit"])
            self.assertEqual(report["flash_decision"], "NO_GO_UNTIL_HARDWARE_RECOVERY_AND_UAT")

    def test_source_requirements_contain_fail_closed_package_hooks(self):
        data = FILE.read_text()
        self.assertIn("usr/libexec/veci/guest-prerm", data)
        self.assertIn("usr/libexec/veci/voucher-prerm", data)
        self.assertIn('require_prerm_hooks=(source_freshness == "CURRENT")', data)
        for package in ("guest", "voucher"):
            helper = ROOT / ("source/veci-app-" + package + "/files/usr/libexec/veci/" + package + "-prerm")
            self.assertTrue(helper.is_file())
            self.assertGreater(helper.stat().st_size, 0)

    def test_no_router_or_publish_actions(self):
        content = FILE.read_text()
        self.assertIn("NO_GO_UNTIL_HARDWARE_RECOVERY_AND_UAT", content)
        self.assertIn("NOT_PERFORMED", content)
        for forbidden in ("sysupgrade -F", "sysupgrade -n", "gh release create", "apk add",
                          "ssh root@", "scp ", "uci set", "--privileged"):
            self.assertNotIn(forbidden, content)


if __name__ == "__main__":
    unittest.main()
