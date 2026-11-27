"""Isolated OEM LAN/WAN adapter contract and ACL tests."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
ADAPTER=Path(__file__).resolve().parents[2]/"rebuild/oem-updated/backend/write-adapter.sh"
class InterfaceWrites(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup); self.d=Path(t.name)
        (self.d/"adapter").write_text(ADAPTER.read_text().replace("/usr/share/libubox/jshn.sh",str(self.d/"jshn")))
        (self.d/"jshn").write_text("""
json_load() { [ -n "$1" ]; }
json_init() { fields=""; }
json_add_string() { fields="$fields\n$1=$2"; }
json_dump() { printf '%b' "$fields" | python3 -c 'import sys,json; print(json.dumps(dict(x.split("=",1) for x in sys.stdin.read().splitlines() if x)))'; }
""")
        self.cmd("jsonfilter",'''#!/usr/bin/env python3
import json,sys
try:
 v=json.load(sys.stdin)[sys.argv[2][2:]]
 print(str(v).lower() if isinstance(v,bool) else v)
except (KeyError,ValueError):sys.exit(1)
''')
        self.cmd("uci",'''#!/bin/sh
[ "$*" = "-q get network.wan.dns" ] && echo '1.1.1.1 9.9.9.9'
''')
        self.cmd("ubus",'''#!/usr/bin/env python3
import json,sys,os
a=sys.argv[1:]
if a[:5]==["-t","3","call","session","access"]:
 q=json.loads(a[5])
 assert q["object"]=="veci.v2.interfaces"
 print(json.dumps({"access":not(os.getenv("DENY")=="1" and q["function"]=="save")}))
elif a[:5]==["-t","20","call","veci.v2.interfaces","status"]:
 print(json.dumps({"ok":True,"revision":"a"*64,"lan":"192.168.1.1","lan_mask":"24","wan_mode":"pppoe","wan":"","wan_mask":"","gateway":""}))
elif a[:5]==["-t","20","call","veci.v2.interfaces","save"]:
 q=json.loads(a[5])
 with open(os.environ["CALLS"],"a") as f:f.write(json.dumps(q)+chr(10))
 print(json.dumps(dict(q,ok=True,lan="wrong" if os.getenv("MISMATCH")=="1" else q["lan"])))
else:sys.exit(99)
''')
    def cmd(self,name,source):
        p=self.d/name;p.write_text(source);p.chmod(0o700)
    def call(self,op,body,**env):
        e=dict(os.environ,PATH=str(self.d)+":"+os.environ["PATH"],CALLS=str(self.d/"calls"))|env
        r=subprocess.run(["sh",str(self.d/"adapter"),op,"a"*32],input=json.dumps(body),text=True,capture_output=True,timeout=6,env=e)
        self.assertEqual(r.returncode,0,r.stderr)
        return json.loads(r.stdout)
    def test_lan_preserves_pppoe_and_wan_replacement(self):
        common={"revision":"a"*64}
        lan=common|{"confirmation":"SAVE_NETWORK","ipaddr":"192.168.2.1","netmask":"24"}
        self.assertEqual(self.call("set_lan_config",lan)["code"],"1")
        for mode in ("dhcp","static"):
            wan=common|{"confirmation":"REPLACE_PPPOE_NEXT_BOOT","proto":mode,"dns_primary":"1.1.1.1","dns_secondary":"9.9.9.9"}
            if mode=="static":wan|={"ipaddr":"10.0.0.2","netmask":"24","gateway":"10.0.0.1"}
            self.assertEqual(self.call("set_wan_config",wan)["code"],"1")
        calls=[json.loads(x) for x in (self.d/"calls").read_text().splitlines()]
        self.assertEqual([x["wan_mode"] for x in calls],["pppoe","dhcp","static"])
        self.assertEqual(calls[0]["lan"],"192.168.2.1")
        self.assertEqual(calls[1]["confirm"],"REPLACE_PPPOE_NEXT_BOOT")
        for patch in ({"revision":"stale"},{"password":"fixture"},{"dns_primary":"8.8.8.8"}):
            self.assertEqual(self.call("set_wan_config",wan|patch)["code"],"-4")
        self.assertEqual(self.call("set_lan_config",lan|{"confirmation":"REPLACE_PPPOE_NEXT_BOOT"})["code"],"-4")
        self.assertEqual(self.call("set_wan_config",wan,DENY="1")["code"],"-4")
        self.assertEqual(len((self.d/"calls").read_text().splitlines()),3)
        self.assertEqual(self.call("set_wan_config",wan,MISMATCH="1")["code"],"-4")
