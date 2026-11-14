"""Real native administration replaces LuCI rather than linking to it."""
import base64
import gzip
import json
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
RPC = ROOT / "source/veci-core/files/rpcd-veci"
WEB = ROOT / "source/veci-core/veci"
ACL = ROOT / "source/veci-core/rpcd-acl.json"
CFG = ROOT / "source/openwrt-we5927.config"


class NativeAdminTests(unittest.TestCase):
    def test_luci_is_removed_in_config_and_all_native_pages(self):
        config = CFG.read_text()
        for line in config.splitlines():
            if line.startswith("CONFIG_PACKAGE_luci") or line.startswith("CONFIG_PACKAGE_liblucihttp"):
                self.assertNotIn("=y", line)
        self.assertNotIn("CONFIG_DEFAULT_luci=y", config)
        self.assertIn("# CONFIG_PACKAGE_luci is not set", config)
        self.assertIn("advancedPage", (WEB / "js/app.js").read_text())
        for page in WEB.rglob("*.js"):
            self.assertNotIn("/cgi-bin/luci", page.read_text(), str(page))
        self.assertNotIn("expert-link", (WEB / "index.html").read_text())

    def test_native_rpc_backup_and_admin_passwd_acl(self):
        source = RPC.read_text()
        self.assertIn("method_backup_start()", source)
        self.assertIn("method_backup_read()", source)
        self.assertIn("method_backup_clear()", source)
        self.assertIn("method_change_admin_password()", source)
        self.assertIn("sysupgrade -b", source)
        self.assertIn("safe_backup_id", source)
        write = json.loads(ACL.read_text())["veci"]["write"]["ubus"]["veci"]
        read = json.loads(ACL.read_text())["veci"]["read"]["ubus"]["veci"]
        for method in ("backupStart", "backupRead", "backupClear", "changeAdminPassword"):
            self.assertIn(method, write)
            self.assertNotIn(method, read)
        reply = subprocess.run(["sh", str(RPC), "list"],
                               capture_output=True, text=True, timeout=3)
        self.assertEqual(reply.returncode, 0, reply.stderr)
        advertised = json.loads(reply.stdout)
        for method in ("backupStart", "backupRead", "backupClear", "changeAdminPassword"):
            self.assertIn(method, advertised)

    def test_backup_stream_is_authenticated_only_and_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            sysupgrade = home / "sysupgrade"
            sysupgrade.write_text(
                "#!/bin/sh\n"
                "[ \"$1\" = '-b' ] || exit 2\n"
                "printf 'non-secret-fixture' | gzip -c > \"$2\"\n"
            )
            sysupgrade.chmod(0o755)
            jsonfilter = home / "jsonfilter"
            jsonfilter.write_text(
                "#!/usr/bin/env python3\n"
                "import json,sys\n"
                "o=json.load(sys.stdin)\n"
                "k=sys.argv[sys.argv.index('-e')+1].removeprefix('@.')\n"
                "print(o.get(k,''))\n"
            )
            jsonfilter.chmod(0o755)
            env = dict(os.environ, PATH=str(home) + os.pathsep + os.environ["PATH"])
            def call(method, payload=None):
                reply = subprocess.run(["sh", str(RPC), "call", method],
                                       input=json.dumps(payload or {}),
                                       env=env, capture_output=True, text=True, timeout=5)
                self.assertEqual(reply.returncode, 0, reply.stderr)
                return json.loads(reply.stdout)
            started = call("backupStart")
            self.assertTrue(started["ok"], started)
            id = started["id"]
            try:
                self.assertEqual(len(id), 8)
                self.assertFalse(call("backupRead", {"id": "../etc", "sequence": 0})["ok"])
                self.assertFalse(call("backupRead", {"id": id, "sequence": 999})["ok"])
                fragment = call("backupRead", {"id": id, "sequence": 0})
                self.assertTrue(fragment["ok"])
                self.assertEqual(gzip.decompress(base64.b64decode(fragment["data"])),
                                 b"non-secret-fixture")
                self.assertEqual(started["size"], len(base64.b64decode(fragment["data"])))
            finally:
                self.assertTrue(call("backupClear", {"id": id})["ok"])
            self.assertFalse(call("backupRead", {"id": id, "sequence": 0})["ok"])


if __name__ == "__main__":
    unittest.main()
