"""Prevent OpenWrt from invoking make for data- and shell-only VeCI v2 packages."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PKGROOT = ROOT / "rebuild/veci-v2/packages"

class VeCIShellPackageBuild(unittest.TestCase):
    def test_source_only_packages_have_empty_compile_override(self):
        for name in ("veci-v2-runtime", "veci-v2-package-manager",
                     "veci-v2-sms", "veci-v2-ipv6", "veci-v2-ui"):
            with self.subTest(package=name):
                path = PKGROOT / name / "Makefile"
                source = path.read_text()
                self.assertIn("define Build/Compile\nendef", source,
                              f"{name} would run make in an empty build directory")
                self.assertIn(f"$(eval $(call BuildPackage,{name}))", source)

if __name__ == "__main__":
    unittest.main()
