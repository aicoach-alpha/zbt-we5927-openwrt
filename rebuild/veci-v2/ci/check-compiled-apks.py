"""Verify the exact native VeCI APK outputs specified by the checkout."""
from pathlib import Path
import re
import sys


PACKAGES = Path(__file__).resolve().parents[1] / "packages"
REQUIRED = ("veci-v2-runtime", "veci-v2-package-manager", "veci-v2-sms",
            "veci-v2-ipv6", "veci-v2-ui")


def check(apk_dir):
    for name in REQUIRED:
        recipe = (PACKAGES / name / "Makefile").read_text()
        version, = re.findall(r"^PKG_VERSION:=([0-9][0-9A-Za-z._-]*)$", recipe, re.M)
        release, = re.findall(r"^PKG_RELEASE:=([1-9][0-9]*)$", recipe, re.M)
        path = apk_dir / f"{name}-{version}-r{release}.apk"
        if path.is_symlink() or not path.is_file() or not path.stat().st_size:
            raise SystemExit(f"MISSING_COMPILED_APK:{path}")
        print(f"COMPILED_APK={path.name}")


if __name__ == "__main__":
    check(Path(sys.argv[1]))
