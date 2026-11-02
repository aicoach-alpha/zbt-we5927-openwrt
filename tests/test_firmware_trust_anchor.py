import hashlib
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "source/veci-default-ui"
PUB = PACKAGE / "files/etc/veci/firmware-keys/veci-20261102.pub"
EXPECTED = "68a7270d6464cca4b9282f5cf7fa4a84482816fc5e9c0a47c7ae0793fa81e25a"

class TrustAnchorTests(unittest.TestCase):
    def test_public_key_pinned(self):
        self.assertEqual(hashlib.sha256(PUB.read_bytes()).hexdigest(), EXPECTED)

    def test_package_installs_public_key_and_release_channel(self):
        text = (PACKAGE/"Makefile").read_text()
        self.assertIn("PKG_RELEASE:=4", text)
        self.assertIn("$(1)/etc/veci/firmware-keys/veci-20261102.pub", text)
        self.assertIn("$(1)/etc/opkg/keys/c0465b699a01a426", text)
        self.assertIn("./files/etc/veci/firmware-keys/veci-20261102.pub", text)
        self.assertIn("$(1)/etc/veci-release-channel", text)

    def test_published_channel_opt_in(self):
        self.assertEqual((PACKAGE/"files/etc/veci-release-channel").read_text(), "development\n")
        prepare = (ROOT/"scripts/prepare-veci.sh").read_text()
        self.assertIn("VECI_PUBLISHED_RELEASE:-0",prepare)
        self.assertIn("printf 'published", prepare)

    def test_no_private_signer_material_shipped(self):
        files = [f for f in (PACKAGE/"files").rglob("*") if f.is_file()]
        self.assertFalse(any(f.suffix in (".sec",".key") or
                             "private" in f.name.lower() for f in files))
        self.assertEqual(sum(f.name.endswith(".pub") for f in files), 1)

    def test_finalizer_checks_rootfs_key_fingerprint(self):
        code = (ROOT/"scripts/finalize-veci-cafe-candidate.py").read_text()
        self.assertIn("Embedded firmware trust root fingerprint mismatch",code)
        self.assertIn("OpenWrt firmware verifier trust root fingerprint mismatch",code)
        self.assertIn("OPENWRT_FIRMWARE_TRUST_FILE",code)
        self.assertIn("Embedded firmware release channel invalid",code)
        self.assertIn(EXPECTED,code)
if __name__=="__main__":
    unittest.main()
