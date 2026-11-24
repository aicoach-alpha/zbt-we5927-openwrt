"""Drive the packaged RPC and C transport through a pseudo-terminal modem."""
import json
import os
from pathlib import Path
import pty
import select
import subprocess
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "rebuild/veci-v2/packages/veci-v2-runtime"


class SimUnlock(unittest.TestCase):
    def test_guarded_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            helper = root / "at"
            subprocess.run(["cc", "-Wall", "-Wextra", "-Werror", "-o", helper,
                            ROOT / "source/we5927-lte/src/we5927-at.c"], check=True)
            master, slave = pty.openpty()
            self.addCleanup(os.close, master)
            self.addCleanup(os.close, slave)
            manager = root / "lte"
            manager.write_text('#!/bin/sh\ncase "$1" in\nselector-slot) echo 1;;\nat-port) echo ' +
                               os.ttyname(slave) + ';; esac\n')
            manager.chmod(0o700)
            board = root / "board"
            board.write_text("zbtlink,zbt-we5927\n")
            provider = (RUNTIME / "veci2-sim-lock").read_text()
            for src, dst in {"/usr/sbin/we5927-lte": manager, "/usr/sbin/we5927-at": helper,
                             "/tmp/sysinfo/board_name": board, "/var/lock/we5927-at.lock": root/"lock"}.items():
                provider = provider.replace(src, str(dst))
            filt = root / "jsonfilter"
            filt.write_text('#!/usr/bin/env python3\nimport json,sys\nprint(json.load(sys.stdin)[sys.argv[-1][2:]])\n')
            filt.chmod(0o700)
            env = dict(os.environ, PATH=str(root) + ":" + os.environ["PATH"])
            state = ["SIM PIN", "3"]
            commands = []
            stop = threading.Event()
            def modem():
                pending = b""
                while not stop.is_set():
                    if not select.select([master], [], [], .05)[0]:
                        continue
                    pending += os.read(master, 512)
                    while b"\r" in pending:
                        raw, pending = pending.split(b"\r", 1)
                        command = raw.decode()
                        commands.append(command)
                        if command == "AT+CPIN?":
                            reply = "+CPIN: " + state[0]
                        elif command.startswith("AT+CPINR="):
                            reply = '+CPINR: "' + state[0] + '",' + state[1] + ',10'
                        else:
                            reply = command
                        os.write(master, ("\r\n" + reply + "\r\nOK\r\n").encode())
            thread = threading.Thread(target=modem)
            thread.start()
            try:
                def call(method, **args):
                    result = subprocess.run(["sh", "-c", provider, "provider", "call", method],
                                            input=json.dumps(args), text=True, capture_output=True,
                                            timeout=6, check=True, env=env)
                    self.assertNotIn("4567", result.stdout + result.stderr)
                    return json.loads(result.stdout)
                args = dict(slot="1", mode="pin", remaining="3", code="4567",
                            new_pin="", confirm="UNLOCK_SIM_ONCE")
                self.assertEqual(call("status")["remaining"], 3)
                for key, value in (("slot", "2"), ("confirm", ""), ("remaining", "4"), ("code", "45A7")):
                    self.assertFalse(call("unlock", **dict(args, **{key:value}))["ok"])
                for remaining in ("unknown", "0", "1"):
                    state[1] = remaining
                    self.assertEqual(call("unlock", **args)["error"], "retry_protection")
                self.assertFalse(any(s.startswith("AT+CPIN=") for s in commands))
                state[1] = "3"
                self.assertTrue(call("unlock", **args)["submitted"])
                state[:] = ["SIM PUK", "7"]
                self.assertTrue(call("unlock", **dict(args, mode="puk", code="12345678",
                                                      remaining="7", new_pin="4567"))["submitted"])
                self.assertEqual([s for s in commands if s.startswith("AT+CPIN=")],
                                 ['AT+CPIN="4567"', 'AT+CPIN="12345678","4567"'])
                state[0] = "READY"
                self.assertEqual(call("status")["mode"], "ready")
            finally:
                stop.set()
                thread.join()
