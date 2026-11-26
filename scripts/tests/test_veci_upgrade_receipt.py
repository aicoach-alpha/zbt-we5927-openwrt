"""Exercise manual and OTA receipt binding with a local download and a dummy installer."""
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

CGI = Path(__file__).resolve().parents[2] / "rebuild/veci-v2/packages/veci-v2-ui/files/www/cgi-bin/veci2-verify"


class UpgradeReceipt(unittest.TestCase):
    def test_manual_and_release_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sub = {"/sbin/sysupgrade": "installer", "/usr/libexec/veci2-verify-image": "verify",
                   "/etc/veci2-update-policy": "policy", "/var/run/veci2-upgrade.receipt": "receipt"}
            code = CGI.read_text()
            for real, fake in sub.items():
                code = code.replace(real, str(root / fake))
            (root / "policy").write_text("manual\n")
            image = b"VeCI fixture\x00\xff"
            digest = hashlib.sha256(image).hexdigest()
            (root / "fixture").write_bytes(image)
            marker = root / "installed"
            for name, body in {
                    "verify": 'test "$(sha256sum "$1" | cut -d" " -f1)" = "$2"',
                    "ubus": "echo '{}'", "jsonfilter": "echo true",
                    "uclient-fetch": 'cat "$FIXTURE"', "installer": 'cp "$1" "$MARKER"'}.items():
                script = root / name
                script.write_text("#!/bin/sh\n" + body + "\n")
                script.chmod(0o700)
            for applet in ("head", "dd", "timeout"):
                (root / applet).symlink_to(shutil.which("busybox"))
            env = dict(os.environ, HTTPS="on", REQUEST_METHOD="POST", CONTENT_TYPE="application/octet-stream",
                       FIXTURE=str(root / "fixture"), MARKER=str(marker), PATH=f"{root}:{os.environ['PATH']}")
            def request(query, ticket="", tag="rc1", asset="router.bin"):
                prefix = ("1"*32 + digest + ticket).encode()
                payload = f"{len(image)}\n{tag}\n{asset}\n".encode() if query.startswith("stable") else image
                body = prefix + payload
                response = subprocess.check_output(["busybox", "ash", "-c", code], input=body, timeout=8,
                    env=dict(env, QUERY_STRING=query, CONTENT_LENGTH=str(len(body))))
                return json.loads(response.split(b"\r\n\r\n")[1])
            for verify, apply in (("", "apply"), ("stable", "stable-apply")):
                ticket = request(verify)["ticket"]
                rejected = "verification_expired_or_replaced"
                if verify:
                    self.assertEqual(request(apply, ticket, tag="rc2")["error"], rejected)
                    self.assertEqual(request(apply, ticket, asset="other.bin")["error"], rejected)
                self.assertTrue(request(apply, ticket)["accepted"])
                for _ in range(100):
                    if marker.exists() and marker.read_bytes() == image:
                        break
                    time.sleep(.05)
                self.assertEqual(marker.read_bytes(), image)
                marker.unlink()
                self.assertEqual(request(apply, ticket)["error"], rejected)
