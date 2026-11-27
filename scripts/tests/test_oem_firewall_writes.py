"""OEM firewall contract fixtures; mock ubus, native libubox JSON handling."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
ADAPTER=Path(__file__).resolve().parents[2]/"rebuild/oem-updated/backend/write-adapter.sh"
PREFIX=os.environ.get("VECI_LIBUBOX_PREFIX","")
@unittest.skipUnless(PREFIX and Path(PREFIX,"bin/jshn").is_file(),"native libubox required")
class FirewallWrites(unittest.TestCase):
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
exit 1
''')
        self.cmd("ubus",'''#!/usr/bin/env python3
import json,sys,os
a=sys.argv[1:]
if a[:5]==["-t","3","call","session","access"]:
 q=json.loads(a[5]);assert q["object"]=="veci.v2.firewall"
 print(json.dumps({"access":os.getenv("DENY")!="1"}))
elif a[:4]==["-t","20","call","veci.v2.firewall"]:
 method=a[4];q=json.loads(a[5])
 with open(os.environ["CALLS"],"a") as f:f.write(json.dumps([method,q])+chr(10))
 mismatch=os.getenv("MISMATCH")=="1"
 r={"ok":True}
 if method=="setDefaults":r.update(drop_invalid="0" if mismatch else q["drop_invalid"],synflood_protect=q["syn_flood"])
 elif method=="setOffload":r.update(flow_offloading=q["enabled"],flow_offloading_hw="1" if mismatch else "0")
 elif method=="setDmz":r["dmz_destination"]="192.168.1.99" if mismatch else "" if q["destination"]=="DISABLE" else q["destination"]
 elif method=="addForward":r["forwards"]=[{"name":"veci_port_tcp_8082","destination":"192.168.1.99" if mismatch else q["destination"],"destination_port":str(q["to_port"]),"source_port":str(q["from_port"])}]
 elif method=="deleteForward":r["forwards"]=[{"name":q["name"]}] if mismatch else []
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


    def test_firewall_writes_and_response_checks(self):
        rev="a"*64
        cases=[
          ("set_fw_setting",{"revision":rev,"confirmation":"SAVE_FIREWALL_DEFAULTS","drop_invalid":"1","syn_flood":"1"}),
          ("set_nat_acceleration",{"revision":rev,"confirmation":"SAVE_SOFTWARE_OFFLOAD","status":"1"}),
          ("set_dmz",{"enabled":"1","ipaddr":"192.168.1.22","sport":"1-65535","confirmation":"ENABLE_DMZ_192.168.1.22"}),
          ("set_dmz",{"enabled":"0","confirmation":"DISABLE_DMZ"}),
          ("set_redirect_dnat",{"action":"ADD_FORWARD","src_dport":"8082","dest_port":"80","proto":"tcp","dest_ip":"192.168.1.22","src":"wan","dest":"lan","enabled":"1","confirmation":"FORWARD_8082"}),
          ("set_redirect_dnat",{"action":"DELETE_FORWARD","name":"veci_port_tcp_8082","confirmation":"DELETE_veci_port_tcp_8082"})]
        for op,body in cases:
            self.assertEqual(self.call(op,body)["code"],"1",(op,body))
            self.assertEqual(self.call(op,body,MISMATCH="1")["code"],"-4",(op,body))
        for op,body in cases:
            self.assertEqual(self.call(op,body|{"confirmation":"wrong"})["code"],"-4")
        self.assertEqual(self.call(cases[0][0],cases[0][1],DENY="1")["code"],"-4")
        self.assertEqual(len((self.d/"calls").read_text().splitlines()),12)
