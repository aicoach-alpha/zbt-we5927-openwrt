"""OEM client policy contract fixtures; mock ubus, native libubox JSON handling."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
ADAPTER=Path(__file__).resolve().parents[2]/"rebuild/oem-updated/backend/write-adapter.sh"
PREFIX=os.environ.get("VECI_LIBUBOX_PREFIX","")
@unittest.skipUnless(PREFIX and Path(PREFIX,"bin/jshn").is_file(),"native libubox required")
class ClientPolicyWrites(unittest.TestCase):
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
 q=json.loads(a[5]);assert q["object"]=="veci.v2.firewall"
 print(json.dumps({"access":os.getenv("DENY")!="1"}))
elif a[:4]==["-t","20","call","veci.v2.firewall"]:
 method=a[4];q=json.loads(a[5])
 mismatch=os.getenv("MISMATCH")=="1"
 mac="02:00:00:00:00:01"
 r={"ok":True,"revision":"a"*64}
 if method=="status":
  r["blocked_macs"]=[mac]
 elif method in ("aclStatus","parentStatus"):
  row={"slot":"1","mac":mac,"enabled":"1"}
  if method=="parentStatus":row.update(start_time="08:00:00",stop_time="09:00:00",weekdays="Monday Friday",timezone="UTC")
  r["rules"]=[row]
 elif method=="setMacBlock":
  r["blocked_macs"]= ["02:00:00:00:00:09"] if mismatch else q["addresses"].split()
 elif method in ("saveAcl","saveParent"):
  row={"slot":q["slot"],"mac":q["mac"],"enabled":"9" if mismatch else q["enabled"]}
  if method=="saveParent":row.update(start_time=q["start_time"],stop_time=q["stop_time"],weekdays=q["weekdays"],timezone="UTC")
  r["rules"]=[row] if q["action"]=="save" or mismatch else []
 else:sys.exit(99)
 if method not in ("status","aclStatus","parentStatus"):
  with open(os.environ["CALLS"],"a") as f:f.write(json.dumps([method,q])+chr(10))
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


    def test_client_policy_mutations_and_receipts(self):
        rev="a"*64
        mac="02:00:00:00:00:01"; other="02:00:00:00:00:02"
        acl=dict(revision=rev,slot="1",mac=mac,enabled="1",action="save",confirmation="SAVE_LAN_ACL")
        parent=acl|dict(confirmation="SAVE_PARENT_SCHEDULE",start_time="08:00:00",stop_time="09:00:00",weekdays="Monday Friday")
        cases=[
          ("set_mac_blacklist",dict(revision=rev,confirmation="SAVE_MAC_BLOCK",mac_blacklist=[mac,other,mac])),
          ("set_mac_blacklist",dict(revision=rev,confirmation="SAVE_MAC_BLOCK",mac_blacklist=[])),
          ("set_wifi_client",dict(revision=rev,confirmation="BLOCK_CLIENT",macaddr=other,operation="REJECT")),
          ("set_wifi_client",dict(revision=rev,confirmation="UNBLOCK_CLIENT",macaddr=mac,operation="ACCEPT")),
          ("set_acl_rule",acl),
          ("set_acl_rule",acl|dict(action="delete",confirmation="DELETE_LAN_ACL")),
          ("set_acl_status",dict(revision=rev,slot="1",enabled="0",confirmation="SAVE_LAN_ACL")),
          ("set_parents_ctrl_rule",parent),
          ("set_parents_ctrl_rule",parent|dict(action="delete",confirmation="DELETE_PARENT_SCHEDULE")),
          ("set_parents_ctrl_status",dict(revision=rev,slot="1",enabled="0",confirmation="SAVE_PARENT_SCHEDULE"))]
        for op,body in cases:
            self.assertEqual(self.call(op,body)["code"],"1",(op,body))
            self.assertEqual(self.call(op,body,MISMATCH="1")["code"],"-4",(op,body))
        calls=[json.loads(x) for x in (self.d/"calls").read_text().splitlines()]
        self.assertEqual(len(calls),20)
        self.assertEqual(calls[0][1]["addresses"],mac+" "+other)
        self.assertEqual(calls[4][1]["addresses"],mac+" "+other)
        self.assertEqual(calls[6][1]["addresses"],"")
        self.assertEqual(calls[12][1]["mac"],mac)
        self.assertEqual(calls[18][1]["weekdays"],"Monday Friday")
        for op,body in cases:
            self.assertEqual(self.call(op,body|{"confirmation":"wrong"})["code"],"-4")
        self.assertEqual(self.call("set_wifi_client",cases[2][1]|{"revision":"stale"})["code"],"-4")
        self.assertEqual(self.call("set_acl_status",cases[6][1]|{"revision":"stale"})["code"],"-4")
        self.assertEqual(self.call("set_mac_blacklist",cases[0][1]|{"mac_blacklist":["01:00:00:00:00:01"]})["code"],"-4")
        self.assertEqual(self.call("set_acl_rule",acl,DENY="1")["code"],"-4")
        self.assertEqual(len((self.d/"calls").read_text().splitlines()),20)
