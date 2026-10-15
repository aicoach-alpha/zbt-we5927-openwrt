#!/usr/bin/env python3
"""Exercise the REAL 0.2.2 post-APK config recovery shell function.

Uses temporary harmless fixtures; no package install, network or router access.
"""
import hashlib
import os
import pathlib
import subprocess
import tempfile

SOURCE = pathlib.Path("scripts/veci-physical-core-022-signed-deploy-20261015.sh").read_text()
BEGIN = "reconcile_config_after_upgrade() {"
END = "\nrestore_files() {"
assert SOURCE.count(BEGIN) == 1 and SOURCE.count(END) == 1
FN = SOURCE.split(BEGIN, 1)[1].split(END, 1)[0]
FN = BEGIN + FN
BASE = """set -eu
CONF="$1"
BACKUP="$2"
CONFIG_SHA="$3"
PACKAGED_CONFIG_SHA="$4"
WORK="$5"
sha() { sha256sum "$1" | awk '{print $1}'; }
check() { [ -f "$1" ] && [ ! -L "$1" ] && [ "$(sha "$1")" = "$2" ]; }
backup_ok() { check "$BACKUP/veci.config" "$CONFIG_SHA"; }
fail() { printf 'VECI_022_DEPLOY=blocked\\nVECI_022_REASON=%s\\n' "$1"; exit 1; }
"""
RUN = BASE + FN + "\nreconcile_config_after_upgrade\n"

def h(s):
    return hashlib.sha256(s).hexdigest()

def test_one(label, current, backup_corrupt=False, symlink=False):
    with tempfile.TemporaryDirectory() as work:
        root = pathlib.Path(work)
        live = root / "veci"
        backup = root / "backup"
        backup.mkdir()
        original = b"config core 'main'\n\toption profile 'physical'\n"
        default = b"config core 'main'\n\toption profile 'auto'\n"
        (backup / "veci.config").write_bytes(b"tampered" if backup_corrupt else original)
        if symlink:
            target = root / "target"
            target.write_bytes(current)
            live.symlink_to(target)
        else:
            live.write_bytes(current)
        result = subprocess.run(
            ["sh", "-c", RUN, "--", str(live), str(backup), h(original), h(default), str(root)],
            text=True, capture_output=True, check=False,
        )
        if label == "original":
            assert result.returncode == 0, result.stderr
            assert "VECI_022_CONFIG_PRESERVATION=unchanged" in result.stdout
            assert live.read_bytes() == original
        elif label == "package_default":
            assert result.returncode == 0, result.stderr
            assert "VECI_022_CONFIG_PRESERVATION=restored_from_verified_backup" in result.stdout
            assert live.read_bytes() == original
            assert (live.stat().st_mode & 0o777) == 0o600
        else:
            assert result.returncode != 0, (label, result.stdout)
            assert "VECI_022_DEPLOY=blocked" in result.stdout
            assert live.read_bytes() == current
            assert not (root / "veci.restore").exists()
            if label == "unexpected":
                assert "postinstall_config_unexpected_drift" in result.stdout
            if label == "bad_backup":
                assert "config_backup_integrity_failed" in result.stdout
            if label == "symlink":
                assert "postinstall_config_not_regular" in result.stdout
        assert (backup / "veci.config").read_bytes() == (b"tampered" if backup_corrupt else original)
        print("VECI_022_CONFIG_CASE=pass", label)

def main():
    original = b"config core 'main'\n\toption profile 'physical'\n"
    default = b"config core 'main'\n\toption profile 'auto'\n"
    test_one("original", original)
    test_one("package_default", default)
    test_one("unexpected", b"new and unknown config")
    test_one("bad_backup", default, backup_corrupt=True)
    test_one("symlink", default, symlink=True)
    assert SOURCE.index("reconcile_config_after_upgrade\nlive_checks") > SOURCE.index(
        'apk --no-network --keys-dir "$WORK/keys" add "$WORK/$NEW"'
    )
    assert SOURCE.count('check "$CONF" "$PACKAGED_CONFIG_SHA"') == 1
    assert 'PACKAGED_CONFIG_SHA=63518b50a5cc75eafceea120424e8125194310ac8829f0a5a3e16ab6a172ae54' in SOURCE
    print("VECI_022_CONFIG_CONTRACT=pass")

if __name__ == "__main__":
    main()
