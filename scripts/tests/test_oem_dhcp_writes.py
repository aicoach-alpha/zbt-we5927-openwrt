"""OEM DHCP contract fixtures; mock ubus, native libubox JSON handling."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
ADAPTER=Path(__file__).resolve().parents[2]/"rebuild/oem-updated/backend/write-adapter.sh"
PREFIX=os.environ.get("VECI_LIBUBOX_PREFIX","")
@unittest.skipUnless(PREFIX and Path(PREFIX,"bin/jshn").is_file(),"native libubox required")
class DhcpWrites(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup); self.d=Path(t.name)
        (self.d/"adapter").write_text(ADAPTER.read_text().replace("/usr/share/libubox/jshn.sh",str(Path(PREFIX,"share/libubox/jshn.sh"))))
        self.cmd("jsonfilter",r'''#!/usr/bin/env python3
import json,re,sys
try:
 v=json.load(sys.stdin)
 for key in re.findall(r'\.([a-zA-Z0-9_]+)|\[([0-9]+)\]',sys.argv[2]):
  v=v[key[0]] if key[0] else v[int(key[1])]
 print(str(v).lower() if isinstance(v,bool) else v)
except (KeyError,IndexError,ValueError,TypeError):sys.exit(1)
''')
        self.cmd("uci",'''#!/bin/sh
case "$*" in "-q get dhcp.lan.leasetime") echo 1h;; "-q get dhcp.lan.dhcp_option") exit 1;; *) exit 99;; esac
''')
        self.cmd("ubus",'''#!/usr/bin/env python3
import json,sys,os
a=sys.argv[1:]
if a[:5]==["-t","3","call","session","access"]:
 q=json.loads(a[5]);assert q["object"]=="veci.v2.dhcp"
 print(json.dumps({"access":os.getenv("DENY")!="1"}))
elif a[:4]==["-t","20","call","veci.v2.dhcp"]:
 method=a[4];q=json.loads(a[5])
 if method=="status":
  print(json.dumps({"ok":True,"revision":"a"*64,"leases":[{"index":0,"mac":"02:11:22:33:44:55","ip":"192.168.1.20"}]}))
 else:
  with open(os.environ["CALLS"],"a") as f:f.write(json.dumps([method,q])+chr(10))
  print(json.dumps({"ok":os.getenv("REJECT")!="1"}))
else:sys.exit(99)
''')
    def cmd(self,n,s):
        p=self.d/n;p.write_text(s);p.chmod(0o700)
    def call(self,op,body,**env):
        e=dict(os.environ,PATH=str(self.d)+":"+str(Path(PREFIX,"bin"))+":"+os.environ["PATH"],LD_LIBRARY_PATH=str(Path(PREFIX,"lib"))+":"+os.environ.get("LD_LIBRARY_PATH",""),CALLS=str(self.d/"calls"))|env
        r=subprocess.run(["busybox","ash",str(self.d/"adapter"),op,"a"*32],input=json.dumps(body),text=True,capture_output=True,timeout=8,env=e)
        self.assertEqual(r.returncode,0,r.stderr)
        return json.loads(r.stdout)
    def test_pool_reservations_and_acl(self):
        pool=dict(dhcp_start="100",dhcp_end="200",dhcp_lease="3600",dhcp_enabled="1",revision="a"*64,confirmation="SAVE_DHCP_POOL")
        add=dict(mac="02:11:22:33:44:55",ip="192.168.1.20",name="fixture")
        delete=dict(maclist=["02:11:22:33:44:55"],revision="a"*64,confirmation="DELETE_RESERVATION")
        for op,body in (("set_dhcp_config",pool),("set_static_dhcp",add),("delete_static_dhcp",delete)):
            self.assertEqual(self.call(op,body)["code"],"1")
        calls=[json.loads(x) for x in (self.d/"calls").read_text().splitlines()]
        self.assertEqual([x[0] for x in calls],["setPool","add","delete"])
        self.assertEqual(calls[0][1]["limit"],"100")
        self.assertEqual(calls[0][1]["lease"],"3600s")
        self.assertEqual(calls[2][1]["confirmation"],"DELETE_LEASE_0")
        for op,body in (("set_dhcp_config",pool|{"dhcp_end":"99"}),("set_static_dhcp",add|{"leasetime":"3h"}),("delete_static_dhcp",delete|{"revision":"stale"}),("delete_static_dhcp",delete|{"maclist":["02:11:22:33:44:55","02:11:22:33:44:56"]})):
            self.assertEqual(self.call(op,body)["code"],"-4")
        self.assertEqual(self.call("set_dhcp_config",pool,DENY="1")["code"],"-4")
        self.assertEqual(len((self.d/"calls").read_text().splitlines()),3)
        self.assertEqual(self.call("set_static_dhcp",add,REJECT="1")["code"],"-4")
