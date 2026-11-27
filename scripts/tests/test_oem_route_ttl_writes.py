"""OEM route and TTL contract fixtures; mock ubus, native libubox JSON handling."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
ADAPTER=Path(__file__).resolve().parents[2]/"rebuild/oem-updated/backend/write-adapter.sh"
PREFIX=os.environ.get("VECI_LIBUBOX_PREFIX","")
@unittest.skipUnless(PREFIX and Path(PREFIX,"bin/jshn").is_file(),"native libubox required")
class RoutingWrites(unittest.TestCase):
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
        self.cmd("ubus",'''#!/usr/bin/env python3
import json,sys,os
a=sys.argv[1:]
if a[:5]==["-t","3","call","session","access"]:
 q=json.loads(a[5]);assert q["object"] in ("veci.v2.routes","veci.v2.firewall")
 print(json.dumps({"access":os.getenv("DENY")!="1"}))
elif a[:3]==["-t","20","call"]:
 method=a[4];q=json.loads(a[5]);bad=os.getenv("MISMATCH")=="1"
 with open(os.environ["CALLS"],"a") as f:f.write(json.dumps([method,q])+chr(10))
 r={"ok":True}
 if method=="save":
  r["entries"]=[{"section":"veci2_route_"+q["name"],"target":"192.0.2.0/32" if bad else q["prefix"],"interface":q["interface"],"gateway":q["gateway"],"table":q["table"]}]
 elif method=="remove":r["entries"]=[{"section":"veci2_route_"+q["name"]}] if bad else []
 elif method=="setTtl":r.update(enabled=q["enabled"],ttl=q["ttl"],runtime="unknown" if bad else "rule_present" if q["enabled"]=="1" else "rule_absent")
 else:sys.exit(99)
 print(json.dumps(r))
else:sys.exit(99)
''')
    def cmd(self,n,s):
        p=self.d/n;p.write_text(s);p.chmod(0o700)
    def call(self,op,body,**env):
        e=dict(os.environ,PATH=str(self.d)+":"+str(Path(PREFIX,"bin"))+":"+os.environ["PATH"],LD_LIBRARY_PATH=str(Path(PREFIX,"lib"))+":"+os.environ.get("LD_LIBRARY_PATH",""),CALLS=str(self.d/"calls"))|env
        r=subprocess.run(["busybox","ash",str(self.d/"adapter"),op,"a"*32],input=json.dumps(body),text=True,capture_output=True,timeout=8,env=e)
        self.assertEqual(r.returncode,0,r.stderr)
        return json.loads(r.stdout)


    def test_route_and_ttl_receipts(self):
        rev="a"*64
        route=dict(revision=rev,name="office",confirmation="SAVE_ROUTE",target="192.0.2.0",netmask="255.255.255.0",interface="wan",gateway="192.168.1.2")
        cases=[("set_static_route",route),("set_static_route",dict(revision=rev,name="office",confirmation="DELETE_ROUTE",name_delete="1")),("set_ttl",dict(revision=rev,ttl_enabled="1",ttl_cnt="64",confirmation="ENABLE_FORWARD_TTL")),("set_ttl",dict(revision=rev,ttl_enabled="0",confirmation="DISABLE_FORWARD_TTL"))]
        for op,body in cases:
            self.assertEqual(self.call(op,body)["code"],"1",(op,body))
            self.assertEqual(self.call(op,body,MISMATCH="1")["code"],"-4")
        for patch in (dict(netmask="255.0.255.0"),dict(metric="10"),dict(confirmation="wrong")):
            self.assertEqual(self.call("set_static_route",route|patch)["code"],"-4")
        self.assertEqual(self.call("set_static_route",route,DENY="1")["code"],"-4")
        calls=[json.loads(x) for x in (self.d/"calls").read_text().splitlines()]
        self.assertEqual(len(calls),8)
        self.assertEqual(calls[0][1]["prefix"],"192.0.2.0/24")
