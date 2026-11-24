"""Exercise a paused manual upload and retry against the packaged CGI."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

WWW = Path(__file__).resolve().parents[2] / "rebuild/veci-v2/packages/veci-v2-ui/files/www"


class ManualUploadTimeoutTests(unittest.TestCase):
    def test_stalled_body_releases_lock_and_removes_partial_image(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, script in {
                "verify": "echo sysupgrade_test_failed >&2\nexit 1",
                "ubus": "echo '{}'",
                "jsonfilter": "cat >/dev/null\necho true",
            }.items():
                command = root / name
                command.write_text("#!/bin/sh\n" + script + "\n")
                command.chmod(0o700)
            source = (WWW / "cgi-bin/veci2-verify").read_text()
            # Use a short real deadline. Every other command runs on the host
            # except ACL transport and the rejecting verifier fixture.
            source = source.replace("timeout 90 head", "timeout 1 head").replace(
                "/usr/libexec/veci2-verify-image", str(root / "verify")).replace(
                "/tmp/veci2-upload.", str(root / "upload."))
            env = dict(os.environ, PATH=f"{root}:" + os.environ["PATH"], HTTPS="on",
                       REQUEST_METHOD="POST", CONTENT_TYPE="application/octet-stream",
                       QUERY_STRING="", CONTENT_LENGTH="100")
            header = b"1" * 32 + b"a" * 64
            args = ["sh", "-c", source]
            with subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, env=env) as proc:
                try:
                    proc.stdin.write(header + b"x")
                    proc.stdin.flush()
                    proc.wait(timeout=5)  # Leave the connection open during the deadline.
                    response = proc.stdout.read()
                finally:
                    proc.kill()
            headers, payload = response.split(b"\r\n\r\n")
            self.assertIn(b"408 Request Timeout", headers)
            self.assertEqual(json.loads(payload), {"error": "upload_timeout"})
            self.assertFalse(list(root.glob("upload.*")))
            with (root / "verify").open() as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            retry = subprocess.run(args, input=header + b"abcd", capture_output=True,
                                   check=True, timeout=4, env=env)
            self.assertIn(b"sysupgrade_test_failed", retry.stdout)
