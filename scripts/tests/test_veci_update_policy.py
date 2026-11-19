"""Run the packaged policy provider and both installation paths in a temporary filesystem."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

PACKAGES = Path(__file__).resolve().parents[2] / "rebuild/veci-v2/packages"


class PolicyTest(unittest.TestCase):
    def test_saved_policy_controls_both_apply_paths(self):
        runtime = PACKAGES / "veci-v2-runtime"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy = root / "policy"
            policy.write_bytes((runtime / "update-policy.default").read_bytes())
            receipt = root / "receipt"
            lock = root / "verifier"
            lock.touch()
            board = root / "board"
            board.write_text("zbtlink,zbt-we5927\n")
            def isolated(source):
                return source.read_text().replace("/etc/veci2-update-policy", str(policy)).replace(
                    "/var/run/veci2-upgrade.receipt", str(receipt)).replace(
                    "/usr/libexec/veci2-verify-image", str(lock)).replace("/tmp/sysinfo/board_name", str(board))
            rpc = isolated(runtime / "veci2-update-policy")
            cgi = isolated(PACKAGES / "veci-v2-ui/files/www/cgi-bin/veci2-verify")
            for name, script in {"jsonfilter": '''#!/usr/bin/env python3
import json, sys
if "-s" in sys.argv:
    print(json.loads(sys.argv[2])["mode"])
else:
    print("true")
''', "ubus": "#!/bin/sh\necho '{}'",
                                 }.items():
                path = root / name
                path.write_text(script)
                path.chmod(0o700)
            env = dict(os.environ, PATH=f"{root}:" + os.environ["PATH"])
            def call(method, mode=""):
                return json.loads(subprocess.check_output(["sh", "-c", rpc, "rpc", "call", method],
                                  input=json.dumps({"mode":mode}), text=True, env=env, timeout=3))
            def apply(query):
                tail = b"1\nv1\nimage.bin\n" if query == "stable-apply" else b"x"
                body = b"1"*32 + b"a"*64 + b"b"*64 + tail
                result = subprocess.check_output(["sh", "-c", cgi], input=body, timeout=3,
                    env=dict(env, HTTPS="on", REQUEST_METHOD="POST", CONTENT_TYPE="application/octet-stream",
                             QUERY_STRING=query, CONTENT_LENGTH=str(len(body))))
                return json.loads(result.split(b"\r\n\r\n")[1])
            self.assertEqual(call("status")["mode"], "manual")
            self.assertEqual(call("save", "automatic")["error"], "invalid_mode")
            with lock.open() as held:
                fcntl.flock(held, fcntl.LOCK_EX)
                self.assertEqual(call("save", "verify_only")["error"], "upgrade_busy")
            receipt.write_text("old ticket")
            self.assertEqual(call("save", "verify_only")["mode"], "verify_only")
            self.assertFalse(receipt.exists())
            for operation in ("apply", "stable-apply"):
                self.assertEqual(apply(operation)["error"], "installation_locked")
            self.assertEqual(call("save", "manual")["mode"], "manual")
            self.assertEqual(apply("apply")["error"], "verification_expired_or_replaced")
            policy.unlink()
            self.assertEqual(apply("stable-apply")["error"], "installation_locked")
