"""Exercise the native manual-upload CGI with a failing verifier on the host."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

WWW = Path(__file__).resolve().parents[2] / "rebuild/veci-v2/packages/veci-v2-ui/files/www"


class UpgradeFeedbackTests(unittest.TestCase):
    def test_rejected_upload_reports_only_known_failure_categories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            verifier = root / "verify"
            for name, script in {
                "verify": 'echo "private detail" >&2\necho "$REASON" >&2\nexit 1\n',
                "jsonfilter": 'cat >/dev/null\necho true\n',
                "ubus": 'echo "{}"\n',
            }.items():
                command = root / name
                command.write_text("#!/bin/sh\n" + script)
                command.chmod(0o700)
            cgi = (WWW / "cgi-bin/veci2-verify").read_text().replace(
                "/usr/libexec/veci2-verify-image", str(verifier))
            image = b"test"
            body = b"1" * 32 + hashlib.sha256(image).hexdigest().encode() + image
            env = dict(os.environ, HTTPS="on", REQUEST_METHOD="POST", QUERY_STRING="",
                       CONTENT_TYPE="application/octet-stream", CONTENT_LENGTH=str(len(body)),
                       PATH=f"{root}:" + os.environ["PATH"])
            for reason, expected in [
                ("incompatible_flash_layout", "incompatible_image"),
                ("invalid_signature", "signature_failed"),
                ("anchor_mismatch", "trust_anchor_failed"),
                ("image_changed", "digest_failed"),
                ("sysupgrade_test_failed", "sysupgrade_test_failed"),
                ("private detail", "image_verification_failed"),
            ]:
                with self.subTest(reason=reason):
                    result = subprocess.run(["sh", "-c", cgi], input=body, capture_output=True,
                                            env=dict(env, REASON=reason), check=True, timeout=3)
                    headers, payload = result.stdout.split(b"\r\n\r\n")
                    self.assertIn(b"422 Unprocessable Entity", headers)
                    self.assertEqual(json.loads(payload), {"error": expected})
