"""Exercise isolated native profile retirement, never actual router UCI."""
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

R=Path(__file__).resolve().parents[2]/"rebuild/veci-v2/packages/veci-v2-runtime"

class LegacyTunnel(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup); self.d=Path(t.name)
        self.cfg=self.d/"network"
        self.original={"vpn1":{"proto":"pptp","auto":"1","key":"fixture-secret"},"vpn2":{"proto":"l2tp","auto":"1"},"vpn3":{"proto":"n2n","auto":"1"},"wan":{"proto":"pptp","auto":"1"},"lan":{"proto":"static"}}
        self.cfg.write_text(json.dumps(self.original))
        (self.d/"board").write_text("zbtlink,zbt-we5927\n")
        (self.d/"jshn").write_text("""
json_load() { [ -n "$1" ]; }
json_get_var() { case "$2" in revision) v="$REVISION";; confirmation) v="$CONFIRM";; name) v="$NAME";; protocol) v="$PROTO";; *) return 1;; esac; export "$1=$v"; }
json_init() { :; }
json_add_array() { :; }
json_close_array() { :; }
json_add_object() { :; }
json_close_object() { :; }
json_add_boolean() { printf '%s=%s\\n' "$1" "$2"; }
json_add_string() { printf '%s=%s\\n' "$1" "$2"; }
json_dump() { :; }
""")
        s=(R/"veci2-addon").read_text()
        for a,b in (("/tmp/sysinfo/board_name","board"),("/usr/share/libubox/jshn.sh","jshn"),("/usr/libexec/veci2-addon-profiles","profiles")):
            s=s.replace(a,str(self.d/b))
        (self.d/"rpc").write_text(s)
        s=(R/"veci2-addon-profiles").read_text().replace("/etc/config/network",str(self.cfg)).replace("/var/lock/veci2-ipv6.lock",str(self.d/"lock"))
        (self.d/"profiles").write_text(s)
        u=self.d/"uci"
        u.write_text("""#!/usr/bin/env python3
import os,sys,json
from pathlib import Path
cfg=Path(os.environ["FIXTURE_CFG"])
data=json.loads(cfg.read_text())
args=sys.argv[1:]
if args[:1]==["-q"]: args=args[1:]
stage=None
if args[:1]==["-t"]:
 stage=Path(args[1])/"delta";args=args[2:]
op,*rest=args
if op=="changes":
 if os.getenv("PENDING")=="1":print("pending")
elif op=="show":
 for name,profile in data.items():print("network."+name+".proto='"+profile["proto"]+"'")
elif op=="get":
 parts=rest[0].split(".")
 try:print("interface" if len(parts)==2 and parts[1] in data else data[parts[1]][parts[2]])
 except (KeyError,IndexError):sys.exit(1)
elif op=="set":
 assert stage is not None
 key,value=rest[0].split("=",1)
 assert key.endswith(".auto") and value=="0"
 stage.write_text(key.split(".")[1])
elif op=="commit":
 assert stage is not None and rest==["network"]
 data[stage.read_text()]["auto"]="0"
 cfg.write_text(json.dumps(data))
 if os.getenv("FAIL_COMMIT")=="1":sys.exit(1)
else:sys.exit(99)
""")
        u.chmod(0o700)
    def run_rpc(self,method,**env):
        args=dict(PATH=str(self.d)+":"+os.environ["PATH"],FIXTURE_CFG=str(self.cfg),REVISION=hashlib.sha256(self.cfg.read_bytes()).hexdigest(),CONFIRM="DISABLE_LEGACY_TUNNEL_NEXT_BOOT",NAME="vpn1",PROTO="pptp")
        args.update(env)
        return subprocess.run(["sh",str(self.d/"rpc"),"call",method],input="{}",text=True,capture_output=True,timeout=6,env=dict(os.environ,**args))
    def test_inventory_and_three_disabled_startups(self):
        r=self.run_rpc("legacyTunnelStatus")
        self.assertIn("activation_supported=0",r.stdout)
        self.assertNotIn("fixture-secret",r.stdout)
        self.assertNotIn("name=wan",r.stdout)
        for name,proto in (("vpn1","pptp"),("vpn2","l2tp"),("vpn3","n2n")):
            r=self.run_rpc("disableLegacyTunnel",NAME=name,PROTO=proto)
            self.assertIn("ok=1",r.stdout,r.stderr)
            self.assertEqual(json.loads(self.cfg.read_text())[name]["auto"],"0")
        expected=json.loads(json.dumps(self.original))
        for name in ("vpn1","vpn2","vpn3"):expected[name]["auto"]="0"
        self.assertEqual(json.loads(self.cfg.read_text()),expected)
    def test_fail_closed_and_rollback(self):
        for args,error in (({"NAME":"wan"},"profile_unavailable"),({"REVISION":"stale"},"stale_configuration"),({"CONFIRM":"ENABLE"},"confirmation_required"),({"PROTO":"n2n"},"protocol_mismatch"),({"PENDING":"1"},"pending_changes"),({"FAIL_COMMIT":"1"},"commit_failed")):
            r=self.run_rpc("disableLegacyTunnel",**args)
            self.assertIn(error,r.stdout,r.stderr)
            self.assertEqual(json.loads(self.cfg.read_text()),self.original)

    def test_oem_adapter_protocol_scope_and_acl(self):
        # Resolve from the repository, independent of working directory.
        adapter=Path(__file__).resolve().parents[2]/"rebuild/oem-updated/backend/write-adapter.sh"
        (self.d/"adapter").write_text(adapter.read_text().replace("/usr/share/libubox/jshn.sh",str(self.d/"adapter-jshn")))
        (self.d/"adapter-jshn").write_text("""
json_load() { [ -n "$1" ]; }
json_init() { fields=""; }
json_add_string() { fields="$fields\n$1=$2"; }
json_dump() {
 printf '%b' "$fields" | python3 -c 'import sys,json; print(json.dumps(dict(x.split("=",1) for x in sys.stdin.read().splitlines() if x)))'
}
""")
        f=self.d/"jsonfilter"
        f.write_text("""#!/usr/bin/env python3
import sys,json
try:
 v=json.load(sys.stdin)[sys.argv[2][2:]]
 print(str(v).lower() if isinstance(v,bool) else v)
except (KeyError,ValueError):sys.exit(1)
""");f.chmod(0o700)
        u=self.d/"ubus"
        u.write_text("""#!/usr/bin/env python3
import json,sys,os
args=sys.argv[1:]
if args[:2]==["-t","3"] and args[2:5]==["call","session","access"]:
 a=json.loads(args[5])
 assert a["object"]=="veci.v2.addon" and a["function"]=="disableLegacyTunnel"
 print(json.dumps({"access":os.getenv("DENY")!="1"}))
elif args[:2]==["-t","20"] and args[2:5]==["call","veci.v2.addon","disableLegacyTunnel"]:
 with open(os.environ["CALLS"],"a") as f: f.write(args[5]+chr(10))
 print('{"ok":true}')
else:sys.exit(99)
""");u.chmod(0o700)
        def call(op,**patch):
            body=dict(name="vpn1",revision="a"*64,enabled="0",confirmation="DISABLE_LEGACY_TUNNEL_NEXT_BOOT")
            deny=patch.pop("deny","0")
            body.update(patch)
            return subprocess.run(["sh",str(self.d/"adapter"),op,"a"*32],input=json.dumps(body),text=True,capture_output=True,timeout=5,env=dict(os.environ,PATH=str(self.d)+":"+os.environ["PATH"],CALLS=str(self.d/"calls"),DENY=deny))
        for proto in ("pptp","l2tp","n2n"):
            r=call("set_"+proto)
            self.assertEqual(json.loads(r.stdout)["code"],"1",r.stderr)
        calls=[json.loads(x) for x in (self.d/"calls").read_text().splitlines()]
        self.assertEqual([x["protocol"] for x in calls],["pptp","l2tp","n2n"])
        self.assertTrue(all(set(x)=={"protocol","name","revision","confirmation"} for x in calls))
        for patch in ({"enabled":"1"},{"confirmation":"ENABLE"},{"key":"fixture-key"},{"name":"bad.name"},{"deny":"1"}):
            r=call("set_pptp",**patch)
            self.assertEqual(json.loads(r.stdout)["code"],"-4",r.stderr)
        self.assertEqual(len((self.d/"calls").read_text().splitlines()),3)
