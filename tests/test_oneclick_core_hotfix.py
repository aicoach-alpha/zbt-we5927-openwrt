"""Offline integration tests only; no router access or firmware flash."""
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "releases/veci-core-r4-hotfix/veci-core-r4.tar.gz"
CHECKSUMS = ROOT / "releases/veci-core-r4-hotfix/SHA256SUMS"
PS1 = ROOT / "scripts/veci-oneclick-update.ps1"
APPLY = ROOT / "scripts/veci-core-apply.sh"
PIN = "81853a6b8b710a26a2427d1176751bf781bc7243" # Immutable archived r4 bundle, not current firmware source pin.


class OneClickCoreTests(unittest.TestCase):
    def test_bundle_sha_and_paths(self):
        sha = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
        self.assertIn(sha, CHECKSUMS.read_text())
        self.assertIn(sha, PS1.read_text())
        self.assertLess(ARCHIVE.stat().st_size, 1024 * 1024)
        with tarfile.open(ARCHIVE, "r:gz") as tar:
            members = tar.getmembers()
            files = {m.name for m in members if m.isfile()}
            self.assertIn("www/veci/index.html", files)
            self.assertIn("www/veci/veci-core-commit.txt", files)
            self.assertIn("usr/libexec/rpcd/veci", files)
            self.assertIn("usr/share/rpcd/acl.d/veci.json", files)
            self.assertTrue(all(not m.issym() and not m.islnk() for m in members))
            self.assertTrue(all(not m.name.startswith("/") and ".." not in Path(m.name).parts for m in members))
            marker = tar.extractfile("www/veci/veci-core-commit.txt").read().decode().strip()
        self.assertEqual(PIN, marker)
        self.assertEqual(PIN, "81853a6b8b710a26a2427d1176751bf781bc7243")

    def test_windows_runner_never_flashes_and_preserves_http(self):
        script = PS1.read_text()
        self.assertIn("Invoke-WebRequest -Uri $ArchiveUrl", script)
        self.assertIn("Get-FileHash", script)
        self.assertIn("scp.exe", script)
        self.assertIn("root@", script)
        self.assertIn("Type UPDATE", script)
        self.assertIn("veci-core-commit.txt", script)
        self.assertIn("Core r4 marker mismatch", script)
        self.assertIn("rollback", script)
        self.assertNotRegex(script, r"(?m)^\s*(?:sysupgrade|uci set|fw_setenv)\s")
        self.assertNotIn("StrictHostKeyChecking=no", script)
        apply = APPLY.read_text()
        self.assertNotIn("sysupgrade", apply)
        self.assertNotIn("uci set", apply)
        self.assertNotIn("uhttpd restart", apply)
        self.assertIn("WRONG_BOARD", apply)

    def test_offline_backup_apply_and_restore(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory(prefix="veci-oneclick-", dir="/tmp") as job:
            root = Path(tmp) / "fake-router"
            (root / "www/veci").mkdir(parents=True)
            (root / "usr/libexec/rpcd").mkdir(parents=True)
            (root / "usr/share/rpcd/acl.d").mkdir(parents=True)
            old = {
                root / "www/veci/index.html": b"OLD VECI WEB UI\n",
                root / "usr/libexec/rpcd/veci": b"#!/bin/sh\necho OLD_RCPD\n",
                root / "usr/share/rpcd/acl.d/veci.json": b'{"old":true}\n',
            }
            for file, blob in old.items():
                file.write_bytes(blob)
            shutil.copyfile(ARCHIVE, Path(job) / "veci-core-r4.tar.gz")
            shim = Path(tmp) / "mockbin"
            shim.mkdir()
            ubus = shim / "ubus"
            ubus.write_text("#!/bin/sh\nif [ \"$1:$2:$3\" = \"call:system:board\" ]; then printf '{\"board_name\":\"zbtlink,zbt-we5927\"}'; exit 0; fi\nif [ \"$1:$2\" = \"list:veci\" ]; then echo veci; exit 0; fi\nexit 1\n")
            ubus.chmod(0o755)
            jsonfilter = shim / "jsonfilter"
            jsonfilter.write_text("#!/bin/sh\necho zbtlink,zbt-we5927\n")
            jsonfilter.chmod(0o755)
            df = shim / "df"
            df.write_text("#!/bin/sh\nprintf 'Filesystem 1024-blocks Used Available Capacity Mounted on\\n'\nprintf 'tmpfs 131072 1024 130048 1%% /overlay\\n'\n")
            df.chmod(0o755)
            smoke_script = APPLY.read_text()
            smoke_script = smoke_script.replace("-C /", "-C " + str(root))
            for name in ("www/veci", "usr/libexec/rpcd/veci", "usr/share/rpcd/acl.d/veci.json"):
                smoke_script = smoke_script.replace("$stage/" + name, "STAGED_" + name.replace("/", "_"))
                smoke_script = smoke_script.replace("/" + name, str(root / name))
                smoke_script = smoke_script.replace("STAGED_" + name.replace("/", "_"), "$stage/" + name)
            smoke_script = smoke_script.replace("/etc/init.d/rpcd restart", "true")
            script = Path(tmp) / "mock-apply.sh"
            script.write_text(smoke_script)
            env = {**os.environ, "PATH": str(shim) + ":" + os.environ["PATH"]}
            def run(action, sha):
                return subprocess.run(["sh", str(script), action, job, sha], env=env, capture_output=True, text=True, timeout=8)
            checksum = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
            pre = run("prepare", checksum)
            self.assertEqual(pre.returncode, 0, pre.stderr)
            self.assertTrue((Path(job) / "backup.tar.gz").is_file())
            bad = run("apply", "0" * 64)
            self.assertNotEqual(bad.returncode, 0)
            self.assertEqual((root / "www/veci/index.html").read_bytes(), old[root / "www/veci/index.html"])
            applied = run("apply", checksum)
            self.assertEqual(applied.returncode, 0, applied.stderr)
            self.assertEqual((root / "www/veci/veci-core-commit.txt").read_text().strip(), PIN)
            self.assertNotEqual((root / "usr/libexec/rpcd/veci").read_bytes(), old[root / "usr/libexec/rpcd/veci"])
            rolled = run("rollback", checksum)
            self.assertEqual(rolled.returncode, 0, rolled.stderr)
            for name, blob in old.items():
                self.assertEqual(name.read_bytes(), blob)
            self.assertFalse((root / "www/veci/veci-core-commit.txt").exists())


if __name__ == "__main__":
    unittest.main()
