"""Run the packaged CGI with BusyBox ash and a local sysupgrade fixture."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

PACKAGES = Path(__file__).resolve().parents[2] / "rebuild/veci-v2/packages"


class BackupExport(unittest.TestCase):
    def test_export_requires_live_grant_and_intact_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            board = root / "board"
            board.write_text("zbtlink,zbt-we5927\n")
            archive = root / "archive"
            archive.write_bytes(gzip.compress(b"test configuration"))
            marker = root / "sysupgrade-called"
            cgi = root / "export"
            cgi.write_text((PACKAGES / "veci-v2-ui/files/www/cgi-bin/veci2-backup").read_text()
                           .replace("/tmp/sysinfo/board_name", str(board))
                           .replace("/tmp/veci2-backup.", directory + "/veci2-backup."))
            for name, cmd in {
                "ubus": 'echo true',
                "jsonfilter": 'if [ "$GRANT" = expire ] && [ -e "$MARKER" ]; then echo false; else echo "$GRANT"; fi',
                "sysupgrade": 'test "$1" = -b && touch "$MARKER" && cp "$ARCHIVE" "$2"'
            }.items():
                path = root / name
                path.write_text("#!/bin/sh\n" + cmd + "\n")
                path.chmod(0o700)
            def call(grant="true", **override):
                marker.unlink(missing_ok=True)
                env = dict(os.environ, PATH=f"{root}:" + os.environ["PATH"], GRANT=grant, ARCHIVE=str(archive),
                           MARKER=str(marker), HTTPS="on", REQUEST_METHOD="POST", CONTENT_LENGTH="32",
                           CONTENT_TYPE="application/octet-stream")
                env.update(override)
                out = subprocess.check_output(["busybox", "ash", cgi], input=b"1"*32, env=env)
                self.assertFalse(list(root.glob("veci2-backup.*")))
                return out.split(b"\r\n\r\n")
            self.assertIn(b"403 Forbidden", call(HTTPS="")[0])
            self.assertIn(b"403 Forbidden", call("false")[0])
            self.assertFalse(marker.exists())
            self.assertIn(b"403 Forbidden", call("expire")[0])
            headers, content = call()
            self.assertEqual(content, archive.read_bytes())
            self.assertIn(hashlib.sha256(content).hexdigest().encode(), headers)
            archive.write_bytes(b"broken archive")
            self.assertIn(b"500 Internal Server Error", call()[0])
            acl = json.loads((PACKAGES / "veci-v2-runtime/veci2-status-acl.json").read_text())
            self.assertEqual(acl["veci-v2-backup"]["write"]["ubus"]["veci.v2.backup"], ["export"])
