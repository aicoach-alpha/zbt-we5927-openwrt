"""Real source binary, PTY modem and RPC acceptance for USSD (no physical modem)."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "source/we5927-lte/src/we5927-at.c"
PROVIDER = ROOT / "rebuild/veci-v2/packages/veci-v2-runtime/veci2-ussd"
UAT = ROOT / "scripts/uat/test-ussd-host.py"


class UssdAcceptance(unittest.TestCase):
    def test_pty_fake_modem_one_shot_timeout_cancel_and_rejects(self):
        # Disposable jshn-only fixture: CI need not have target libubox installed.
        # The tested shell provider and compiled AT transport remain unmodified.
        with tempfile.TemporaryDirectory(prefix="veci-ussd-jshn-") as directory:
            prefix=Path(directory)
            stub=prefix/"share/libubox/jshn.sh"
            stub.parent.mkdir(parents=True)
            stub.write_text("""json_init() { :; }
json_add_boolean() { export JSHN_B="$2"; }
json_add_int() { export JSHN_N="$2"; }
json_add_string() { export JSHN_S="$2"; }
json_dump() { python3 -c 'import json,os; print(json.dumps({"ok":os.environ.get("JSHN_B")=="1","status":int(os.environ["JSHN_N"]),"response":os.environ["JSHN_S"]}))'; }
""")
            (prefix/"bin").mkdir()
            (prefix/"lib").mkdir()
            outcome = subprocess.run(["python3",str(UAT),str(prefix)],text=True,
                capture_output=True,timeout=25,
                env={**os.environ,"PATH":str(prefix/"bin")+":"+os.environ["PATH"]})
            self.assertEqual(outcome.returncode,0,outcome.stdout+"\n"+outcome.stderr)
            self.assertIn("PASS PTY",outcome.stdout)
            self.assertIn("timeout",outcome.stdout)
            self.assertIn("wrong slot",outcome.stdout)

    def test_at_helper_rejects_input_injection_without_opening_modem(self):
        with tempfile.TemporaryDirectory(prefix="veci-ussd-accept-") as directory:
            output=Path(directory)/"we5927-at"
            subprocess.run(["cc","-Wall","-Wextra","-Werror","-o",str(output),str(HELPER)],
                           check=True,capture_output=True)
            for invalid in ("\n", "*123", "123#", "*1 ;AT#\n",
                            '*1";AT+CFUN=1#\n', "*123#\nEXTRA\n",
                            "x"*40+"\n", "*\n", "#\n", "*#\n",
                            "*🚀#\n", "*12/3#\n"):
                with self.subTest(code=repr(invalid)):
                    proc=subprocess.run([str(output),"/dev/this-modem-does-not-exist","--ussd-stdin","1200"],
                        input=invalid,text=True,capture_output=True,timeout=3)
                    self.assertEqual(proc.returncode,2,(repr(invalid),proc.stdout,proc.stderr))
                    self.assertEqual(proc.stdout,"")
            accepted=subprocess.run([str(output),"/dev/this-modem-does-not-exist","--ussd-stdin","1200"],
                    input="*123#\n",text=True,capture_output=True,timeout=3)
            self.assertEqual(accepted.returncode,3,accepted.stderr)
            self.assertNotIn("*123#",accepted.stdout+accepted.stderr)

    def test_rpc_is_scoped_and_fails_closed(self):
        data = PROVIDER.read_text()
        acl=json.loads((ROOT/"rebuild/veci-v2/packages/veci-v2-runtime/veci2-status-acl.json").read_text())
        scoped=acl["veci-v2-lte"]
        self.assertEqual(scoped["read"]["ubus"]["veci.v2.ussd"],["status"])
        self.assertEqual(set(scoped["write"]["ubus"]["veci.v2.ussd"]),{"send","cancel"})
        for marker in ("SEND_USSD_ONCE","CANCEL_USSD","previous_request_pending",
                       "sim_changed","modem_busy","unsupported_board","response_unconfirmed"):
            self.assertIn(marker,data)
        self.assertIn("--ussd-stdin",data)
        self.assertNotIn("AT+CFUN",data)
        subprocess.run(["busybox","ash","-n",str(PROVIDER)],check=True,capture_output=True)


if __name__=="__main__":
    unittest.main()
