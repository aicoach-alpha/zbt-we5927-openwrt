"""Exercise exact bundled LTE APN policy against disposable UCI; never call real router."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "rebuild/veci-v2/packages/veci-v2-runtime/veci2-lte-policy"
MANAGER = ROOT / "source/we5927-lte/files/usr/sbin/we5927-lte"


class ApnIntegration(unittest.TestCase):
    def test_actual_oem_apn_validator(self):
        script = MANAGER.read_text()
        match = re.search(r'^valid_apn\(\) \{\n.*?^\}', script, flags=re.M | re.S)
        self.assertIsNotNone(match)
        for candidate, good in {
            "internet":True, "m2m.private-01":True, "MY_OPERATOR":True,
            "":False, "space in apn":False, 'x";AT+CFUN=1':False,
            "ab/../../tmp":False, "x" * 101:False, "x" * 100:True,
            "apn\nbad":False, "apn'bad":False, "🚀":False,
        }.items():
            with self.subTest(value=repr(candidate[:20])):
                result = subprocess.run(["busybox","ash","-c",match.group(0) + '\nvalid_apn "$1"',"_",candidate],
                    text=True,capture_output=True,timeout=5)
                self.assertEqual(result.returncode == 0, good, result.stderr)

    def test_real_rpc_provider_uci_staging_and_no_modem_restart(self):
        with tempfile.TemporaryDirectory(prefix="veci-apn-test-") as directory:
            root = Path(directory)
            board = root / "board"
            board.write_text("zbtlink,zbt-we5927\n")
            state = root / "uci-state.json"
            state.write_text(json.dumps({
                "we5927_lte.main":"modem", "we5927_lte.main.apn":"internet",
                "we5927_lte.main.auto_failover":"0", "we5927_lte.main.ping_interval":"10",
                "we5927_lte.main.sim":"1",
            }))
            manager = root / "lte"
            manager.write_text("""#!/bin/sh
case "$1" in
validate-apn)
  case "$2" in ''|*[!A-Za-z0-9._-]*) exit 1;; esac
  test "$(printf %s "$2" | wc -c)" -le 100 ;;
selector-slot) echo 1 ;;
*) echo unexpected-manager-action >&2; exit 9 ;;
esac
""")
            manager.chmod(0o700)
            uci = root / "uci"
            uci.write_text("""#!/usr/bin/env python3
import os,json,sys
p=os.environ["FAKE_UCI_STATE"]
data=json.load(open(p))
args=sys.argv[1:]
if args and args[0]=='-q':args.pop(0)
stage=None
if args and args[0]=='-t': stage=args[1]+'/delta'; args=args[2:]
if not args:sys.exit(2)
op=args.pop(0)
if op=='get':
 value=data.get(args[0])
 if value is None:sys.exit(1)
 print(value)
elif op=='changes':
 pass
elif op=='set':
 key,value=args[0].split('=',1)
 assert stage;open(stage,'w').write(json.dumps({key:value}))
elif op=='commit':
 data.update(json.load(open(stage)));open(p,'w').write(json.dumps(data))
else:
 print('unsupported-uci:',op,file=sys.stderr);sys.exit(2)
""")
            uci.chmod(0o700)
            filt = root / "jsonfilter"
            filt.write_text("""#!/usr/bin/env python3
import json,sys
args=sys.argv[1:]
raw=args[args.index('-s')+1]
key=args[args.index('-e')+1].removeprefix('@.')
val=json.loads(raw).get(key)
if val is None:sys.exit(1)
print(val)
""")
            filt.chmod(0o700)
            provider = POLICY.read_text().replace("/tmp/sysinfo/board_name", str(board))
            provider = provider.replace("/usr/sbin/we5927-lte",str(manager)).replace("/etc/config/we5927_lte",str(state)).replace("/var/lock/veci2-lte-policy.lock",str(root/"policy.lock")).replace("/var/run/veci2-reboot-requested",str(root/"reboot-pending"))
            provider_file = root / "veci-lte-policy"
            provider_file.write_text(provider)
            env = dict(os.environ, FAKE_UCI_STATE=str(state),PATH=str(root)+":"+os.environ["PATH"])
            def call(method, apn=None):
                inputdata=json.dumps({"apn":apn}) if apn is not None else ""
                p=subprocess.run(["busybox","ash",str(provider_file),"call",method],
                                 input=inputdata, text=True,capture_output=True,env=env,timeout=8)
                self.assertEqual(p.returncode,0,p.stderr)
                return json.loads(p.stdout)
            self.assertEqual(call("status")["configured_apn"],"internet")
            for bad in (";", "A B", "../secret", 'x";AT+CFUN=1', "x"*101):
                before=state.read_text()
                result=call("setApn",bad)
                self.assertFalse(result["ok"],bad)
                self.assertEqual(before,state.read_text(),bad)
            valid="m2m.private-01"
            result=call("setApn",valid)
            self.assertTrue(result["ok"],result)
            self.assertEqual(result["configured_apn"],valid)
            self.assertEqual(call("status")["configured_apn"],valid)
            self.assertEqual(json.loads(state.read_text())["we5927_lte.main.apn"],valid)
            self.assertNotIn("unexpected-manager-action", json.dumps(result))
            # Existing failover policy must not change as a side effect of APN update.
            self.assertEqual(json.loads(state.read_text())["we5927_lte.main.auto_failover"],"0")

    def test_private_sim_and_apn_acl_and_board_safety(self):
        policy = POLICY.read_text()
        sim = (ROOT/"rebuild/veci-v2/packages/veci-v2-runtime/veci2-sim-lock").read_text()
        acl = json.loads((ROOT/"rebuild/veci-v2/packages/veci-v2-runtime/veci2-status-acl.json").read_text())
        scopes = acl["veci-v2-lte"]
        self.assertIn("setApn",scopes["write"]["ubus"]["veci.v2.lte"])
        self.assertEqual(scopes["write"]["ubus"]["veci.v2.simlock"],["unlock"])
        self.assertIn('UNLOCK_SIM_ONCE',sim)
        self.assertIn("retry_protection",sim)
        self.assertIn('we5927-lte validate-apn',policy)
        for prohibited in ("reboot", "ifdown", "ifup", "AT+CFUN", "gpioctl"):
            self.assertNotIn(prohibited,policy.replace("/var/run/veci2-reboot-requested","").replace("reboot_pending",""))


if __name__ == "__main__":
    unittest.main()
