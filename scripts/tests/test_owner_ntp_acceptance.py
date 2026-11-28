"""Exercise the actual VeCI sysntpd UCI provider against disposable files."""
from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime"
SOURCE=(RUNTIME/"veci2-system-admin").read_text()
JSHN = r'''
json_init() { _json_enabled='';_json_servers=''; }
json_add_boolean() { :; }
json_add_array() { :; }
json_add_string() {
  if [ "$1" = enabled ]; then _json_enabled="$2"; else
    if [ -n "$_json_servers" ]; then _json_servers="$_json_servers,"; fi
    _json_servers="$_json_servers\"$2\""
  fi
}
json_close_array() { :; }
json_dump() { printf '{"ok":true,"enabled":"%s","servers":[%s]}\n' "$_json_enabled" "$_json_servers"; }
'''
UCI = r'''#!/usr/bin/env python3
import json,os,pathlib,sys
cfg=pathlib.Path(os.environ["FAKE_SYSTEM_CFG"])
state=json.loads(cfg.read_text())
args=sys.argv[1:]
if args and args[0]=='-q':args.pop(0)
stage=None
if args and args[0]=='-t':
    stage=pathlib.Path(args[1])/"staged.json"
    args=args[2:]
cmd=args.pop(0)
if cmd=='get':
    key=args[0]
    if key=='system.ntp':print('timeserver')
    elif key=='system.ntp.enabled':print(state['enabled'])
    elif key=='system.ntp.server':print(' '.join(state['servers']))
    else:sys.exit(1)
elif cmd=='changes':
    if pathlib.Path(os.environ["FAKE_PENDING_MARKER"]).exists():
        print("system.ntp.enabled='0'")
elif cmd in ('delete','set','add_list'):
    if stage is None:sys.exit(12)
    data=json.loads(stage.read_text()) if stage.exists() else state
    if cmd=='delete':
        if args[0]!='system.ntp.server':sys.exit(12)
        data['servers']=[]
    elif cmd=='set':
        if args[0]!='system.ntp.enabled=1':sys.exit(12)
        data['enabled']='1'
    elif cmd=='add_list':
        prefix='system.ntp.server='
        if not args[0].startswith(prefix):sys.exit(12)
        data['servers'].append(args[0][len(prefix):])
    stage.write_text(json.dumps(data))
elif cmd=='commit':
    if stage is None or not stage.exists() or args!=['system']:sys.exit(12)
    cfg.write_text(stage.read_text())
else:
    print("invalid uci command",cmd,file=sys.stderr)
    sys.exit(12)
'''


class NtpSourceAcceptance(unittest.TestCase):
    def fixture(self):
        temp=tempfile.TemporaryDirectory(prefix="veci-ntp-")
        self.addCleanup(temp.cleanup)
        root=Path(temp.name)
        board=root/"board"
        board.write_text("zbtlink,zbt-we5927\n")
        cfg=root/"system"
        cfg.write_text(json.dumps({"enabled":"0","servers":["0.pool.ntp.org"]}))
        pending=root/"pending"
        bad_restart=root/"restart-fails-once"
        shim=root/"jshn.sh"
        shim.write_text(JSHN)
        fake_uci=root/"uci"
        fake_uci.write_text(UCI)
        fake_uci.chmod(0o700)
        ntp=root/"sysntpd"
        ntp.write_text("""#!/bin/sh
if [ -e "$FAKE_RESTART_FAIL" ]; then rm -f "$FAKE_RESTART_FAIL"; exit 1; fi
exit 0
""")
        ntp.chmod(0o700)
        filt=root/"jsonfilter"
        filt.write_text("""#!/usr/bin/env python3
import json,sys
args=sys.argv[1:]; raw=args[args.index('-s')+1]
key=args[args.index('-e')+1].removeprefix('@.')
v=json.loads(raw).get(key)
if v is None:sys.exit(1)
print(v)
""")
        filt.chmod(0o700)
        program=root/"provider"
        content=SOURCE.replace("/tmp/sysinfo/board_name",str(board))
        content=content.replace("/usr/share/libubox/jshn.sh",str(shim))
        content=content.replace("/etc/config/system",str(cfg)).replace("/var/run/veci2-reboot-requested",str(root/"reboot-pending"))
        content=content.replace("/etc/init.d/sysntpd",str(ntp))
        program.write_text(content)
        env={**os.environ,
             "PATH":str(root)+":"+os.environ["PATH"],
             "FAKE_SYSTEM_CFG":str(cfg),
             "FAKE_PENDING_MARKER":str(pending),
             "FAKE_RESTART_FAIL":str(bad_restart)}
        def call(method,**fields):
            run=subprocess.run(["busybox","ash",str(program),"call",method],
                input=json.dumps(fields),text=True,capture_output=True,env=env,timeout=8)
            self.assertEqual(run.returncode,0,run.stderr)
            return json.loads(run.stdout)
        return root,cfg,board,pending,bad_restart,call

    def test_real_rpc_ntp_staging_and_rollback(self):
        root,cfg,board,pending,bad_restart,call=self.fixture()
        first=call("ntp")
        self.assertEqual(first["servers"],["0.pool.ntp.org"])
        self.assertEqual(first["enabled"],"0")
        original=cfg.read_bytes()
        good={"first":"0.id.pool.ntp.org","second":"1.id.pool.ntp.org","confirmation":"SET_NTP"}
        for change in [{"confirmation":""},{"second":"0.id.pool.ntp.org"},
                       {"first":"../etc/shadow"},{"first":"a b"},
                       {"first":"bad..host"},{"first":"x"*254},
                       {"first":"bad-.example"},{"first":"a.-bad"},{"first":"valid.example\nother.example"}]:
            data=good|change
            self.assertFalse(call("setNtp",**data)["ok"],data)
            self.assertEqual(cfg.read_bytes(),original)
        (root/"reboot-pending").touch()
        self.assertEqual(call("setNtp",**good)["error"],"reboot_pending")
        (root/"reboot-pending").unlink()
        pending.touch()
        self.assertEqual(call("setNtp",**good)["error"],"pending_system_changes")
        pending.unlink()
        bad_restart.touch()
        self.assertEqual(call("setNtp",**good)["error"],"ntp_apply_failed_rollback_attempted")
        self.assertEqual(cfg.read_bytes(),original)
        changed=call("setNtp",**good)
        self.assertTrue(changed["ok"],changed)
        self.assertEqual(changed["servers"],["0.id.pool.ntp.org","1.id.pool.ntp.org"])
        self.assertEqual(changed["enabled"],"1")
        self.assertEqual(json.loads(cfg.read_text())["servers"],changed["servers"])
        board.write_text("another-board\n")
        self.assertEqual(call("ntp")["error"],"unsupported_board")

    def test_uci_acl_and_no_radio_lte_modification(self):
        acl=json.loads((RUNTIME/"veci2-status-acl.json").read_text())["veci-v2-system"]
        self.assertEqual(acl["write"]["ubus"]["veci.v2.system"],["setNtp","rebootNow"])
        self.assertIn("ntp",acl["read"]["ubus"]["veci.v2.system"])
        self.assertIn("flock -n 9",SOURCE)
        for forbidden in ("ifdown","ifup","wifi reload","AT+CFUN"):
            self.assertNotIn(forbidden,SOURCE)
        subprocess.run(["busybox","ash","-n",str(RUNTIME/"veci2-system-admin")],check=True)


if __name__=="__main__":
    unittest.main()
