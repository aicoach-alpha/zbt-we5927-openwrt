import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "veci-rc-image-integrity.py"
spec = importlib.util.spec_from_file_location("integrity", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class FirmwareAttestationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.image = self.base / "sysupgrade.bin"
        self.image.write_bytes(b"x" * (gate.MIN_IMAGE_BYTES + 1))
        self.meta = self.base / "meta.json"
        self.data = {
            "supported_devices": ["zbtlink,zbt-we5927", "zbt-we5927"],
            "version": {
                "version": "25.12.5",
                "target": "ramips/mt76x8",
                "board": "zbtlink_zbt-we5927",
            },
        }
        self.write_meta()
        self.root = self.base / "root-ramips"
        (self.root / "usr/sbin").mkdir(parents=True)
        self.lte = self.base / "expected-lte.sh"
        self.lte.write_text("manual_reconnect() {\n:; }\nif [ 1 ] && radio_or_link_lost; then\n:; fi\n")
        (self.root / "usr/sbin/we5927-lte").write_bytes(self.lte.read_bytes())
        (self.root / "usr/sbin/veci-wifi-guardian").write_bytes(
            b"#!/bin/sh\n# never reload radio\n"
            b"printf 'auto_recover=0 beacon_verified=0'\n"
        )

    def tearDown(self):
        self.tmp.cleanup()

    def write_meta(self):
        self.meta.write_text(json.dumps(self.data))

    def run_gate(self):
        return gate.attest(self.image, self.meta, self.root, self.lte)

    def test_good_build_not_flash_authorization(self):
        result = self.run_gate()
        self.assertTrue(result["build_integrity_pass"], result["blockers"])
        self.assertEqual(result["image_size_bytes"], gate.MIN_IMAGE_BYTES + 1)
        self.assertEqual(len(result["sha256"]), 64)
        self.assertFalse(result["production_flash_authorized"])
        self.assertFalse(result["image_signature_verified"])

    def test_board_mismatch_fails(self):
        self.data["supported_devices"] = ["some-other-board"]
        self.write_meta()
        self.assertIn("unsupported_board", self.run_gate()["blockers"])

    def test_wrong_target_fails(self):
        self.data["version"]["target"] = "ath79/generic"
        self.write_meta()
        self.assertIn("wrong_target", self.run_gate()["blockers"])

    def test_wrong_version_fails(self):
        self.data["version"]["version"] = "25.12.6"
        self.write_meta()
        self.assertIn("wrong_openwrt_version", self.run_gate()["blockers"])

    def test_image_oversize_fails(self):
        self.image.write_bytes(b"x" * (gate.MTD_FIRMWARE_BYTES + 1))
        self.assertIn("firmware_partition_exceeded", self.run_gate()["blockers"])

    def test_stale_lte_fails(self):
        (self.root / "usr/sbin/we5927-lte").write_text("old script")
        self.assertIn("stale_lte_source", self.run_gate()["blockers"])

    def test_missing_guardian_fails(self):
        (self.root / "usr/sbin/veci-wifi-guardian").unlink()
        self.assertFalse(self.run_gate()["build_integrity_pass"])

    def test_guardian_radio_reload_fails(self):
        with (self.root / "usr/sbin/veci-wifi-guardian").open("ab") as f:
            f.write(b"wifi reload radio0\n")
        self.assertIn("guardian_contains_disruptive_wifi_command",
                      self.run_gate()["blockers"])

    def test_comment_only_radio_reload_does_not_trigger(self):
        with (self.root / "usr/sbin/veci-wifi-guardian").open("ab") as f:
            f.write(b"# wifi reload radio0\n")
        self.assertTrue(self.run_gate()["build_integrity_pass"])

    def test_symlink_image_fails_closed(self):
        link = self.base / "linked.bin"
        link.symlink_to(self.image)
        result = gate.attest(link, self.meta, self.root, self.lte)
        self.assertFalse(result["build_integrity_pass"])

    def test_invalid_metadata_fails_closed(self):
        self.meta.write_text("NOT JSON")
        self.assertFalse(self.run_gate()["build_integrity_pass"])

    def test_no_signing_claim_even_with_spa(self):
        (self.root / "www/veci").mkdir(parents=True)
        (self.root / "www/veci/index.html").write_text("<title>VeCI</title>")
        x = self.run_gate()
        self.assertTrue(x["veci_native_spa_present"])
        self.assertFalse(x["production_flash_authorized"])


if __name__ == "__main__":
    unittest.main()
