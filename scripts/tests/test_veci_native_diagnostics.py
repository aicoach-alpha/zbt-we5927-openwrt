import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "rebuild/veci-v2/packages/veci-v2-runtime"


class NativeDiagnostics(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.board = self.dir / "board"
        self.board.write_text("zbtlink,zbt-we5927\n")
        self.provider = self.dir / "diag"
        self.provider.write_text((RUNTIME / "veci2-diagnostics").read_text().replace(
            "/tmp/sysinfo/board_name", str(self.board)))
        self.provider.chmod(0o700)
        self.env = dict(os.environ, PATH=f"{self.dir}:" + os.environ["PATH"])
        self.command("jsonfilter", '#!/usr/bin/env python3\nimport sys,json\nprint(json.loads(sys.argv[2])["target"])\n')

    def command(self, name, body):
        p = self.dir / name
        p.write_text(body)
        p.chmod(0o700)

    def invoke(self, method, target="router.lan"):
        result = subprocess.run([self.provider, "call", method], input=json.dumps({"target":target}),
                                text=True, capture_output=True, env=self.env, timeout=4, check=True)
        return json.loads(result.stdout)

    def test_logs_limited_and_json_escaped(self):
        script = """#!/usr/bin/env python3
for n in range(100):
    print(str(n) + '"' + chr(92) + chr(27) + 'x'*500)
"""
        for method, name in (("systemLog","logread"), ("kernelLog","dmesg")):
            self.command(name, script)
            result = self.invoke(method)
            self.assertEqual(result["exit_code"], 0)
            self.assertEqual(len(result["lines"]), 80)
            self.assertEqual(result["lines"][0], '20"' + chr(92) + 'x'*316)
            self.assertTrue(all(len(line) == 320 for line in result["lines"]))

    def test_fixed_arguments_and_command_failures(self):
        for method, command, flags in (("lookup","nslookup",[]),("ping","ping",["-c","3","-W","1"]),
                   ("trace","traceroute",["-n","-q","1","-w","1","-m","6"])):
            self.command(command, '#!/bin/sh\nprintf "%s\\n" "$@"\nexit 2\n')
            result = self.invoke(method)
            self.assertEqual(result["lines"], flags + ["router.lan"])
            self.assertEqual(result["exit_code"], 2)

    def test_access_validation_and_contention(self):
        for invalid in ("", "-c", "a b", "a;echo", "x"*254):
            self.assertEqual(self.invoke("ping", invalid)["error"], "invalid_target")
        self.assertEqual(self.invoke("run")["error"], "invalid_method")
        with self.provider.open() as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self.assertEqual(self.invoke("kernelLog")["error"], "busy")
        self.board.write_text("other")
        self.assertEqual(self.invoke("systemLog")["error"], "board_mismatch")
        listed = json.loads(subprocess.check_output([self.provider, "list"]))
        acl = json.loads((RUNTIME / "veci2-diag-acl.json").read_text())
        self.assertEqual(set(acl["veci-v2-diagnostics"]["read"]["ubus"]["veci.v2.diag"]), set(listed))
        self.assertNotIn("unauthenticated", acl)
