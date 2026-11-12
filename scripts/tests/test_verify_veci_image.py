"""Negative-path release validation: no mocked signature is ever reported as real."""
import hashlib
import importlib.util
import pathlib
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "verify_veci_image.py"
spec = importlib.util.spec_from_file_location("veci_image_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class FailClosedImageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = pathlib.Path(self.directory.name)
        self.image = self.root / "candidate.bin"
        self.image.write_bytes(b"not a firmware image")
        self.sha = hashlib.sha256(self.image.read_bytes()).hexdigest()
        self.trust = self.root / "trusted-keys"
        self.trust.mkdir()

    def test_wrong_hash_refused(self):
        with self.assertRaisesRegex(gate.GateError, "SHA-256 mismatch"):
            gate.check_image_file(self.image, "0" * 64)

    def test_bad_hash_encoding_refused(self):
        with self.assertRaisesRegex(gate.GateError, "expected SHA-256"):
            gate.check_image_file(self.image, "not-a-hash")

    def test_missing_image_refused(self):
        with self.assertRaisesRegex(gate.GateError, "unavailable"):
            gate.check_image_file(self.root / "missing.bin", self.sha)

    def test_symlink_refused(self):
        alias = self.root / "alias.bin"
        alias.symlink_to(self.image)
        with self.assertRaisesRegex(gate.GateError, "symlink"):
            gate.check_image_file(alias, self.sha)

    def test_size_limit_refused(self):
        image = self.root / "too-big.bin"
        with image.open("wb") as stream:
            stream.truncate(gate.MTD_MAX + 1)
        with self.assertRaisesRegex(gate.GateError, "overflow"):
            gate.check_image_file(image, "0" * 64)

    def test_wrong_board_refused(self):
        with self.assertRaisesRegex(gate.GateError, "board"):
            gate.check_metadata({
                "supported_devices": ["unrelated,board"],
                "version": {"target": gate.TARGET, "version": gate.VERSION},
            })

    def test_wrong_release_refused(self):
        with self.assertRaisesRegex(gate.GateError, "release"):
            gate.check_metadata({
                "supported_devices": [gate.BOARD],
                "version": {"target": gate.TARGET, "version": "25.12.6"},
            })

    def test_missing_trust_anchor_refused(self):
        with self.assertRaisesRegex(gate.GateError, "contains no keys"):
            gate.verify(self.image, self.sha, self.trust)

    def test_missing_verifier_refused_even_with_key_file(self):
        (self.trust / "existing-router-key.pub").write_text("dummy")
        with self.assertRaisesRegex(gate.GateError, "missing verification tool"):
            gate.verify(self.image, self.sha, self.trust,
                        fwtool="/definitely/missing/fwtool")

    def test_signature_missing_refused(self):
        (self.trust / "existing-router-key.pub").write_text("dummy")
        dummy = self.root / "stub-fwtool"
        dummy.write_text("""#!/bin/sh
if [ "$1" = "-i" ]; then
  echo '{"supported_devices":["zbtlink,zbt-we5927"],"version":{"target":"ramips/mt76x8","version":"25.12.5"}}' > "$2"
  exit 0
fi
# Certificate intentionally absent; fail closed.
exit 1
""")
        dummy.chmod(0o755)
        with self.assertRaisesRegex(gate.GateError, "missing firmware ucert"):
            gate.verify(self.image, self.sha, self.trust, fwtool=str(dummy))


if __name__ == "__main__":
    unittest.main()
