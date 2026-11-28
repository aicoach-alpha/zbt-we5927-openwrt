"""OEM guest and PPPoE contracts; mock ubus, native libubox JSON handling."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
ADAPTER=Path(__file__).resolve().parents[2]/"rebuild/oem-updated/backend/write-adapter.sh"
PREFIX=os.environ.get("VECI_LIBUBOX_PREFIX","")
@unittest.skipUnless(PREFIX and Path(PREFIX,"bin/jshn").is_file(),"native libubox required")
class GuestPppoeWrites(unittest.TestCase):
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
 q=json.loads(a[5]);assert q["object"] in ("veci.v2.guest","veci.v2.addon","veci.v2.interfaces")
 print(json.dumps({"access":os.getenv("DENY")!="1"}))
elif a[:3]==["-t","20","call"]:
 method=a[4];q=json.loads(a[5]);bad=os.getenv("MISMATCH")=="1"
 with open(os.environ["CALLS"],"a") as f:f.write(method+chr(10))
 r={"ok":True}
 if method=="setNativeStartup":r["enabled_configured"]=(q["enabled"]=="1") != bad
 elif method=="setPortalStartup":r["guest"]="unknown" if bad else "enabled" if q["action"]=="ENABLE_PORTAL_AP" else "disabled"
 elif method=="pppoeAction":r.update(requested=not bad,state="pending_verification",internet_verified=False)
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


    def test_guest_and_pppoe_pending_receipt(self):
        rev="a"*64
        cases=[("set_wifi_guest",dict(mode="native",revision=rev,guest_enabled="1",confirmation="ENABLE_NATIVE_GUEST_NEXT_BOOT")),
               ("set_wifi_guest",dict(mode="native",revision=rev,guest_enabled="0",confirmation="DISABLE_NATIVE_GUEST_NEXT_BOOT")),
               ("set_wifi_guest",dict(expected="disabled",guest_enabled="1",confirmation="ENABLE_PORTAL_AP")),
               ("pppoe_disconnect",dict(revision=rev,confirmation="DISCONNECT_ETHERNET_PPPOE")),
               ("pppoe_reconnect",dict(revision=rev,confirmation="RECONNECT_ETHERNET_PPPOE"))]
        for op,body in cases:
            self.assertEqual(self.call(op,body)["code"],"1",(op,body))
            self.assertEqual(self.call(op,body,MISMATCH="1")["code"],"-4")
            self.assertEqual(self.call(op,body|dict(confirmation="wrong"))["code"],"-4")
        self.assertEqual(self.call(cases[0][0],cases[0][1],DENY="1")["code"],"-4")
