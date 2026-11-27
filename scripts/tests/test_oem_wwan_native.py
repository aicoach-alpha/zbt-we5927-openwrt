"""Native host UCI WWAN lifecycle; firewall compilation and RF are mocked."""
import os
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

SOURCE=Path(__file__).resolve().parents[2]/"rebuild/veci-v2/packages/veci-v2-runtime/veci2-wifi"
UCI=os.environ.get("VECI_HOST_UCI","")

@unittest.skipUnless(UCI and Path(UCI).is_file(),"native host UCI required")
class WwanNative(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d=Path(tmp.name)
        self.cfg=self.d/"config";self.cfg.mkdir()
        self.delta=self.d/"delta";self.delta.mkdir()
        configs={
            "network":"config interface 'lan'\n option proto 'static'\n option ipaddr '192.168.1.1'\nconfig interface 'wan'\n option proto 'dhcp'\n option device 'eth0.2'\nconfig interface 'lte'\n option proto 'dhcp'\n option device 'usb0'\n option metric '5'\n",
            "wireless":"config wifi-device 'radio0'\n option band '2g'\nconfig wifi-iface 'default_radio0'\n option device 'radio0'\n option mode 'ap'\n option network 'lan'\n",
            "firewall":"config defaults\n option forward 'REJECT'\nconfig zone\n option name 'lan'\n list network 'lan'\nconfig zone\n option name 'wan'\n option input 'REJECT'\n option masq '1'\n list network 'wan'\n list network 'lte'\n",
        }
        for c,s in configs.items():(self.cfg/c).write_text(s)
        self.original={x.name:x.read_bytes() for x in self.cfg.iterdir()}
        (self.d/"board").write_text("zbtlink,zbt-we5927\n")
        (self.d/"fw-rpc").touch()
        self.cmd("uci",'#!/bin/sh\nexec "$HOST_UCI" -c "$TEST_CFG" -t "$TEST_DELTA" "$@"\n')
        self.cmd("fw4",'#!/bin/sh\n[ "$*" = check ] || exit 99\n[ "${FAIL_FW:-0}" = 0 ]\n')
        (self.d/"jshn").write_text("""
json_init() { :; }
json_load() { [ -n "$1" ]; }
json_get_var() {
 case "$2" in revision) v="$REVISION";; confirmation) v="$CONFIRM";; action) v="$ACTION";; ssid) v="Fixture AP";; password) v="FixtureOnly123";; *) return 1;; esac
 export "$1=$v"
}
json_add_boolean() { printf '%s=%s\\n' "$1" "$2"; }
json_add_string() { printf '%s=%s\\n' "$1" "$2"; }
json_dump() { :; }
""")
        s=SOURCE.read_text()
        for old,new in (("/etc/config/","config/"),("/tmp/sysinfo/board_name","board"),("/usr/libexec/rpcd/veci.v2.firewall","fw-rpc"),("/usr/share/libubox/jshn.sh","jshn"),("/var/lock/veci2-ipv6.lock","network.lock"),("/var/run/veci2-reboot-requested","reboot-pending")):
            s=s.replace(old,str(self.d)+"/"+new)
        (self.d/"rpc").write_text(s)
        self.env=dict(os.environ,HOST_UCI=UCI,TEST_CFG=str(self.cfg),TEST_DELTA=str(self.delta),PATH=str(self.d)+":"+os.environ["PATH"])
    def cmd(self,name,source):
        p=self.d/name;p.write_text(source);p.chmod(0o700)
    def call(self,method,**env):
        return subprocess.run(["sh",str(self.d/"rpc"),"call",method],input="{}",text=True,capture_output=True,timeout=8,env=dict(self.env,REVISION="",CONFIRM="",ACTION="")|env)
    def revision(self):
        r=self.call("uplinkStatus")
        self.assertEqual(r.returncode,0,r.stderr)
        return next(x.split("=",1)[1] for x in r.stdout.splitlines() if x.startswith("revision="))
    def uci(self,*args):
        r=subprocess.run(["uci","-q",*args],env=self.env,text=True,capture_output=True,timeout=5)
        return r.stdout.strip() if r.returncode==0 else None
    def provision(self,**env):
        args=dict(REVISION=self.revision(),CONFIRM="PROVISION_WWAN_DISABLED");args.update(env)
        return self.call("provisionWwan",**args)
    def test_native_wwan_and_sta_lifecycle(self):
        self.assertIn("provisionable=1",self.call("uplinkStatus").stdout)
        r=self.provision()
        for field in ("eligible=1","configured=0","enabled=0","connection_verified=0"):
            self.assertIn(field,r.stdout,r.stderr)
        for k,v in {"network.wwan.proto":"dhcp","network.wwan.metric":"50","network.wwan.ipv6":"0","network.lte.device":"usb0","network.lte.metric":"5","network.wan.device":"eth0.2","firewall.@zone[1].network":"wan lte wwan","firewall.@zone[0].network":"lan"}.items():
            self.assertEqual(self.uci("get",k),v,k)
        self.assertIsNone(self.uci("get","wireless.veci_uplink"))
        r=self.call("saveUplink",REVISION=self.revision(),CONFIRM="SAVE_UPLINK_DISABLED",ACTION="save")
        self.assertIn("configured=1",r.stdout,r.stderr)
        self.assertIn("enabled=0",r.stdout,r.stderr)
        self.assertNotIn("FixtureOnly123",r.stdout)
        self.assertEqual(self.uci("get","wireless.veci_uplink.disabled"),"1")
        for action,expected in (("enable","1"),("disable","0")):
            r=self.call("saveUplink",REVISION=self.revision(),CONFIRM=action.upper()+"_UPLINK_NEXT_BOOT",ACTION=action)
            self.assertIn("enabled="+expected,r.stdout,r.stderr)
        self.assertEqual(self.uci("get","wireless.default_radio0.mode"),"ap")
    def test_reject_and_rollback(self):
        for env,err in (({"REVISION":"stale"},"stale_configuration"),({"CONFIRM":"wrong"},"confirmation_required"),({"FAIL_FW":"1"},"validation_failed_rollback")):
            r=self.provision(**env)
            self.assertIn(err,r.stdout,r.stderr)
            self.assertEqual({x.name:x.read_bytes() for x in self.cfg.iterdir()},self.original)
        self.uci("set","network.wwan=interface");self.uci("set","network.wwan.proto=static");self.uci("commit","network")
        original={x.name:x.read_bytes() for x in self.cfg.iterdir()}
        self.assertIn("provisionable=0",self.call("uplinkStatus").stdout)
        self.assertIn("foreign_or_unsupported_topology",self.provision().stdout)
        self.assertEqual({x.name:x.read_bytes() for x in self.cfg.iterdir()},original)

    def test_oem_uplink_adapter_scope_and_acl(self):
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
 assert a["object"]=="veci.v2.wifi" and a["function"]=="saveUplink"
 print(json.dumps({"access":os.getenv("DENY")!="1"}))
elif args[:2]==["-t","20"] and args[2:5]==["call","veci.v2.wifi","saveUplink"]:
 with open(os.environ["CALLS"],"a") as f: f.write(args[5]+chr(10))
 print(json.dumps({'ok':True,'enabled':json.loads(args[5])['action']=='enable' and os.getenv('MISMATCH')!='1'}))
else:sys.exit(99)
""");u.chmod(0o700)
        def call(op,**patch):
            body=dict(action="enable",revision="a"*64,confirmation="ENABLE_UPLINK_NEXT_BOOT")
            deny=patch.pop("deny","0")
            mismatch=patch.pop("mismatch","0")
            body.update(patch)
            return subprocess.run(["sh",str(self.d/"adapter"),op,"a"*32],input=json.dumps(body),text=True,capture_output=True,timeout=5,env=dict(os.environ,PATH=str(self.d)+":"+os.environ["PATH"],CALLS=str(self.d/"calls"),DENY=deny,MISMATCH=mismatch))
        for action in ("enable","disable"):
            r=call("set_wifi_apclient",action=action,confirmation=action.upper()+"_UPLINK_NEXT_BOOT")
            self.assertEqual(json.loads(r.stdout)["code"],"1",r.stderr)
        calls=[json.loads(x) for x in (self.d/"calls").read_text().splitlines()]
        self.assertEqual([x["action"] for x in calls],["enable","disable"])
        self.assertTrue(all(set(x)=={"action","revision","confirmation"} for x in calls))
        for patch in ({"action":"save"},{"confirmation":"wrong"},{"password":"fixture-key"},{"deny":"1"}):
            r=call("set_wifi_apclient",**patch)
            self.assertEqual(json.loads(r.stdout)["code"],"-4",r.stderr)
        self.assertEqual(len((self.d/"calls").read_text().splitlines()),2)
        r=call("set_wifi_apclient",mismatch="1")
        self.assertEqual(json.loads(r.stdout)["code"],"-4",r.stderr)
