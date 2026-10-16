#!/usr/bin/env python3
"""Reconstruct immutable WE5927 VeCI Core from the EXACT owner-observed web tree.

Reads only SHA-pinned upstream archives and files in the firmware repository.
No hardware access, firmware flashing, package installation, or modem/SMS action.
Fails closed unless EVERY produced baseline web file matches physical snapshot.
"""
import argparse
import hashlib
import re
import shutil
from pathlib import Path

BASE = {
    "app.css": "b041c36cfa61edbd4ff91cf67b44c1fc8dbd5ca68518dd785ca18a87e8d2bdfd",
    "icons/veci.svg": "77f09bc5ecf4e3122a4226aab940fb4a25cb5e3d0c3a24ad04798ee052d18c97",
    "index.html": "1a30386fd46a4401b58e86ab194ca312ea5783e75f9c09e831f3a9b5f9b08009",
    "js/app.js": "3a7ff6126d03e52c537e9c3e2344e23707eb250c9aa06e316ce4f2ed1e017445",
    "js/lib/api.js": "61f8c5ca16d23ea29281cd98a37bd16cf79d8610eaf762329863a714ce2090be",
    "js/lib/dom.js": "156862836e04810777bc0fc208721c9105c33afcbca265789a441ba75eca6e35",
    "js/lib/format.js": "9cb3c0f8693b510520f7cf51a86eaa0f61eabbb6670ed59e85b3631cae65aa7f",
    "js/lib/icons.js": "3cf9bdf8aa95a23279f4cf5c827a5c2b63f56132cadf9d1e2824bdf98f329ebe",
    "js/pages/apps.js": "a3dd92d62b02fe04045d0ac683fc1339272b9d8cf8cf997c9fd4afba72a83fc6",
    "js/pages/cellular.js": "8f9219c21ca49b44ea5d5a2705fccdde77315249c53c21715974df384d4adef6",
    "js/pages/devices.js": "3d5e9879a146649ecdc88b6c87cc5c2fc605f4ef51c5da15ee4eccb0e9957064",
    "js/pages/home.js": "878d82c8ca4fef3b7bfdf4e6de654a42b93f3e34cb4a6525827da841e7163ba4",
    "js/pages/internet.js": "8d341519b9ec0fe88ffc8f4851dcc290d6f03aea78c0f7fcfb7752551e8c204e",
    "js/pages/network.js": "055b6f2b57e3031238fbdf70d1bf47aacef70bab7545c3654828eaedee02053a",
    "js/pages/security.js": "77c1654761354524897a8fe7a938c9624942c8fc41f7203bbca2088d17f97874",
    "js/pages/system.js": "07e14bde2c12f175b3af79a242e7f1d35c848b37872958f6771cdd74ab9baded",
    "js/pages/wifi.js": "fa63a70a9ce76d0f00800bc5bf0296141bbf4287db624cc08c3c963b01834b03",
    "manifest.json": "1bb66be02dc866ebcfdd45410d69caeb7afa0f4a4459c05c057bb4f9f1e29017",
    "sms-center.css": "fd3b3540109d815d9b3cb5151298af04ef865e55557d8a8a91d9c30f1548fdb2",
}
PATCHED = "b075a4852d3eeb5f717e4db568a0929fc732b225f025a154beb24961a3f85379"
MODULE = "5c1f66b5a5aa292be202897ef538f67ed7933e857ff3e11bcaabb075b75c692d"
LIVE_RPCD = "d08edadd38f0d9b992fc54d879eabf9f797bf54df83fa8c8cf7b59e55b9e99ce"
LIVE_ACL = "d655406fd94214c22cf047bf5fc49e66876365634958be9d25171e6100e6a171"
FIRST_IMPORT = "import { badge, escapeHtml, setBusy } from '../lib/dom.js';\n"
QUOTA_IMPORT = "import { mountOperatorQuota } from '../lib/native-quota.js?v=20261015';\n"
ONLINE = "\t\tif (online) {\n"
QUOTA_CALL = "\t\tmountOperatorQuota({ api, root });\n"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def overlay(src, dst):
    if not src.is_file() or src.is_symlink():
        raise RuntimeError(f"source unavailable: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def main():
    ap = argparse.ArgumentParser()
    for name in ("base", "main", "home", "repo", "dest"):
        ap.add_argument("--" + name, type=Path, required=True)
    ap.add_argument("--version", choices=["0.2.0", "0.2.2"], required=True)
    args = ap.parse_args()
    if args.dest.exists():
        raise RuntimeError("refusing to overwrite destination")
    shutil.copytree(args.base, args.dest)
    root = args.dest / "veci"
    # The deployed 0.2.0 UI is a precise mixture of independently pinned
    # upstream versions, plus the frozen v160 SMS/USSD production page.
    for rel, source in (
        ("js/app.js", args.main / "veci/js/app.js"),
        ("js/pages/apps.js", args.main / "veci/js/pages/apps.js"),
        ("js/pages/home.js", args.home / "veci/js/pages/home.js"),
        ("js/pages/cellular.js", args.repo / "scripts/veci-xl-ussd-v17-staged/cellular-v160.js"),
        ("sms-center.css", args.repo / "scripts/veci-sms-mifi-v159-staged/sms-center.css"),
    ):
        overlay(source, root / rel)
    for old in ("js/lib/quota.js", "js/pages/updates.js"):
        (root / old).unlink(missing_ok=True)
    actual = {str(p.relative_to(root)): sha(p) for p in root.rglob("*") if p.is_file()}
    if actual != BASE:
        failures = [p for p in set(actual) | set(BASE) if actual.get(p) != BASE.get(p)]
        raise RuntimeError(f"physical web source parity failed: {sorted(failures)}")
    print("VECI_PHYSICAL_WEB_PARITY=pass", len(BASE), "exact files")

    # Both the target and downgrade package MUST restore the actually LIVE
    # patched operator quota interface, not the older pre-overlay 0.2.0 UI.
    if args.version in ("0.2.0", "0.2.2"):
        js = root / "js/pages/cellular.js"
        before = js.read_text(encoding="utf-8")
        if before.count(FIRST_IMPORT) != 1 or before.count(ONLINE) != 1:
            raise RuntimeError("Cellular addon anchor drift")
        after = before.replace(FIRST_IMPORT, FIRST_IMPORT + QUOTA_IMPORT, 1)
        after = after.replace(ONLINE, QUOTA_CALL + ONLINE, 1)
        js.write_text(after, encoding="utf-8", newline="")
        if sha(js) != PATCHED:
            raise RuntimeError(f"patched source fingerprint drift: {sha(js)}")
        overlay(args.repo / "scripts/veci-native-quota-overlay/native-quota.js",
                root / "js/lib/native-quota.js")
        if sha(root / "js/lib/native-quota.js") != MODULE:
            raise RuntimeError("native quota module fingerprint drift")
        # No frontend changes beyond two line insertions and one addon.
        stripped = after.replace(QUOTA_IMPORT, "", 1).replace(QUOTA_CALL, "", 1)
        if stripped != before:
            raise RuntimeError("existing SMS/USSD source modified")
        print("VECI_PHYSICAL_SMS_USSD_PRESERVED=pass")
        print("VECI_PHYSICAL_QUOTA_PATCH_SHA256=" + PATCHED)

    # Do not replace the LIVE core RPCD/ACL with historical, generic sources.
    # Each file is owner-provided from an exact physical snapshot and must
    # pass SHA-256 verification before it can enter any public signed APK.
    live = args.repo / "scripts/veci-physical-core-runtime-20261015"
    for source, dest, required in (
        (live / "rpcd-veci", args.dest / "files/rpcd-veci", LIVE_RPCD),
        (live / "veci-acl.json", args.dest / "rpcd-acl.json", LIVE_ACL),
    ):
        if sha(source) != required:
            raise RuntimeError(f"physical backend source integrity failed: {source}")
        overlay(source, dest)
        if sha(dest) != required:
            raise RuntimeError(f"physical backend staged copy drift: {dest}")
    print("VECI_PHYSICAL_CORE_RPCD_SHA256=" + LIVE_RPCD)
    print("VECI_PHYSICAL_CORE_ACL_SHA256=" + LIVE_ACL)

    mk = args.dest / "Makefile"
    build = mk.read_text(encoding="utf-8")
    if build.count("PKG_VERSION:=0.2.0") != 1:
        raise RuntimeError("Unexpected pinned Makefile")
    mk.write_text(build.replace("PKG_VERSION:=0.2.0",
                                "PKG_VERSION:=" + args.version, 1), encoding="utf-8")
    print("VECI_PHYSICAL_CORE_VERSION=" + args.version)


if __name__ == "__main__":
    main()
