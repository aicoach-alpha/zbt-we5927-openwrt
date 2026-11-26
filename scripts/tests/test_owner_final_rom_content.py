"""Fail-closed source-to-SquashFS image mapping for all 39 active core features (USSD retired)."""
import importlib.util
import hashlib
import pathlib
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT=pathlib.Path(__file__).resolve().parents[2]
SOURCE=ROOT/"rebuild/veci-v2/ci/check-all-core-rom.py"
spec=importlib.util.spec_from_file_location("veci_full_rom",SOURCE)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CompleteRomSourceMap(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="veci-39-rom-test-")
        self.addCleanup(self.temp.cleanup)
        self.rom=pathlib.Path(self.temp.name)
        for pairs in module.FEATURES.values():
            for original,inside in pairs:
                destination=self.rom/inside
                destination.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(ROOT/original,destination)
    def test_39_active_sources_have_exact_compiled_image_path_and_bytes(self):
        self.assertEqual(len(module.FEATURES),39)
        self.assertNotIn("lte_ussd",module.FEATURES)
        self.assertEqual(module.check(self.rom),[])
    def test_receipt_binds_each_mapped_payload_to_bytes(self):
        receipt = []
        self.assertEqual(module.check(self.rom, receipt), [])
        self.assertEqual({item["module"] for item in receipt}, set(module.FEATURES))
        self.assertEqual(len(receipt), sum(map(len, module.FEATURES.values())))
        for item in receipt:
            self.assertEqual(item["sha256"], hashlib.sha256((self.rom/item["rom"]).read_bytes()).hexdigest())

    def test_any_missing_runtime_sends_fail_closed(self):
        target=self.rom/"usr/libexec/rpcd/veci.v2.observability"
        self.assertTrue(target.is_file())
        target.unlink()
        errors=module.check(self.rom)
        self.assertIn("ROM_MISSING_OR_WRONG_SIZE:firmware_24x7_observability:usr/libexec/rpcd/veci.v2.observability",errors)
    def test_modified_backend_rejected_even_same_bytes(self):
        target=self.rom/"usr/libexec/rpcd/veci.v2.firewall"
        payload=bytearray(target.read_bytes());payload[5]^=0x01
        target.write_bytes(payload)
        self.assertIn(
          "ROM_DIFFERENT_FROM_VERIFIED_SOURCE:firewall_zones_nat:usr/libexec/rpcd/veci.v2.firewall",
          module.check(self.rom))
    def test_luci_presence_hard_fail_and_no_hardware_claims(self):
        target=self.rom/"www/cgi-bin/luci"
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text("not allowed")
        self.assertIn("LUCI_PRESENT:www/cgi-bin/luci",module.check(self.rom))
        self.assertNotIn("hardware_uat=pass",SOURCE.read_text().lower())
    def _simulate_protected_read(self, target):
        real_read = pathlib.Path.read_bytes

        def read_bytes(path):
            if path == target:
                raise PermissionError("owner-only SquashFS config")
            return real_read(path)
        return read_bytes

    def test_protected_ipv6_config_uses_only_sudo_sha256sum_and_keeps_permissions(self):
        target=self.rom/"etc/config/veci2_ipv6"
        target.chmod(0o600)
        before=target.stat().st_mode & 0o777
        sha=hashlib.sha256(target.read_bytes()).hexdigest()
        result=subprocess.CompletedProcess(
            args=["sudo", "-n", "sha256sum", "--", str(target)],
            returncode=0,stdout=f"{sha}  {target}\\n",stderr="")
        with mock.patch.object(pathlib.Path, "read_bytes",
                               autospec=True, side_effect=self._simulate_protected_read(target)):
            with mock.patch.object(module.subprocess, "run", return_value=result) as sudo_hash:
                self.assertEqual(module.check(self.rom),[])
        sudo_hash.assert_called_once_with(
            ["sudo", "-n", "sha256sum", "--", str(target)],
            capture_output=True,text=True,timeout=12,check=True)
        self.assertEqual(target.stat().st_mode & 0o777,before)
        self.assertIn("subprocess.run",SOURCE.read_text())

    def test_protected_wrong_hash_still_fails(self):
        target=self.rom/"etc/config/veci2_ipv6"
        result=subprocess.CompletedProcess(
            args=["sudo", "-n", "sha256sum", "--", str(target)],
            returncode=0,stdout="0"*64+"  "+str(target)+"\\n",stderr="")
        with mock.patch.object(pathlib.Path,"read_bytes",
                               autospec=True,side_effect=self._simulate_protected_read(target)):
            with mock.patch.object(module.subprocess,"run",return_value=result):
                errors=module.check(self.rom)
        self.assertIn("ROM_DIFFERENT_FROM_VERIFIED_SOURCE:system_ipv6_off_by_default:etc/config/veci2_ipv6",
                      errors)

    def test_protected_unavailable_or_invalid_root_hash_fails_closed(self):
        target=self.rom/"etc/config/veci2_ipv6"
        with mock.patch.object(pathlib.Path,"read_bytes",
                               autospec=True,side_effect=self._simulate_protected_read(target)):
            with mock.patch.object(module.subprocess,"run",
                                   side_effect=subprocess.CalledProcessError(1,["sudo","sha256sum"])):
                errors=module.check(self.rom)
            self.assertTrue(any("ROM_HASH_UNAVAILABLE:system_ipv6_off_by_default:etc/config/veci2_ipv6" in x
                                for x in errors))
            invalid=subprocess.CompletedProcess(
                args=[],returncode=0,stdout="not-a-real-sha256\\n",stderr="")
            with mock.patch.object(module.subprocess,"run",return_value=invalid):
                errors=module.check(self.rom)
            self.assertTrue(any("PROTECTED_ROM_HASH_INVALID" in x for x in errors))

    def test_cannot_substitute_feature_names(self):
        self.assertEqual(set(module.FEATURES),
                         {x["id"] for x in __import__("json").loads(module.CONTRACT.read_text())["required_core"]})

if __name__=="__main__":unittest.main()
