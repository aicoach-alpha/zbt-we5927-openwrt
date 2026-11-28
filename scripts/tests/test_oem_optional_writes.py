"""OEM optional services contract fixtures; mock ubus, native libubox JSON handling."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
ADAPTER=Path(__file__).resolve().parents[2]/"rebuild/oem-updated/backend/write-adapter.sh"
PREFIX=os.environ.get("VECI_LIBUBOX_PREFIX","")
@unittest.skipUnless(PREFIX and Path(PREFIX,"bin/jshn").is_file(),"native libubox required")
class OptionalWrites(unittest.TestCase):
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
 q=json.loads(a[5]);assert q["object"]=="veci.v2.addon"
 print(json.dumps({"access":os.getenv("DENY")!="1"}))
elif a[:4]==["-t","20","call","veci.v2.addon"]:
 method=a[4];q=json.loads(a[5]);bad=os.getenv("MISMATCH")=="1"
 with open(os.environ["CALLS"],"a") as f:f.write(json.dumps([method,q])+chr(10))
 if method=="saveSqm":r=dict(q,ok=True,state="disabled",enabled="0",download="9" if bad else q["download"])
 elif method in ("setOptionalStartup","setOpenvpnStartup"):
  r=dict(q,ok=True,state="unknown" if bad else "enabled" if q["enabled"]=="1" else "disabled")
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


    def test_optional_receipts(self):
        rev="a"*64
        cases=[
         ("set_qos",dict(revision=rev,confirmation="SAVE_SQM_NEXT_BOOT",interface="usb0",download="10000",upload="2000",qdisc="cake",script="piece_of_cake.qos")),
         ("set_qos_status",dict(revision=rev,confirmation="ENABLE_SQM_NEXT_BOOT",qos_enabled="1")),
         ("set_qos_status",dict(revision=rev,confirmation="DISABLE_SQM_NEXT_BOOT",qos_enabled="0")),
         ("set_ddns",dict(revision=rev,confirmation="DISABLE_DDNS_NEXT_BOOT",enabled="0")),
         ("set_openvpn",dict(revision=rev,confirmation="DISABLE_OPENVPN_NEXT_BOOT",enabled="0"))]
        for op,body in cases:
            self.assertEqual(self.call(op,body)["code"],"1",(op,body))
            self.assertEqual(self.call(op,body,MISMATCH="1")["code"],"-4")
            self.assertEqual(self.call(op,body|{"confirmation":"wrong"})["code"],"-4")
        self.assertEqual(self.call(cases[0][0],cases[0][1],DENY="1")["code"],"-4")
        self.assertEqual(len((self.d/"calls").read_text().splitlines()),10)
