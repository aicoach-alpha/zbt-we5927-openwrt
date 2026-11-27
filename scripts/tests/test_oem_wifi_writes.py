"""OEM Wi-Fi contract fixtures; mock ubus, native libubox JSON handling."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
ADAPTER=Path(__file__).resolve().parents[2]/"rebuild/oem-updated/backend/write-adapter.sh"
PREFIX=os.environ.get("VECI_LIBUBOX_PREFIX","")
@unittest.skipUnless(PREFIX and Path(PREFIX,"bin/jshn").is_file(),"native libubox required")
class WifiWrites(unittest.TestCase):
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
 q=json.loads(a[5]);assert q["object"]=="veci.v2.wifi"
 print(json.dumps({"access":os.getenv("DENY")!="1"}))
elif a[:4]==["-t","20","call","veci.v2.wifi"]:
 method=a[4];q=json.loads(a[5])
 with open(os.environ["CALLS"],"a") as f:f.write(method+chr(10))
 mismatch=os.getenv("MISMATCH")=="1"
 r={"ok":True}
 if method=="setSsid":r["ssid"]="wrong" if mismatch else bytes.fromhex(q["ssid_hex"]).decode()
 elif method=="setChannel":r["configured_channel"]="99" if mismatch else q["channel"]
 elif method=="setAutoChannel":r["configured_channel"]="99" if mismatch else "auto"
 elif method=="setVisibility":r["configured_visible"]=(q["action"]=="SHOW_SSID") != mismatch
 elif method=="setAuth":r["configured_encryption"]="none" if mismatch else q["mode"]
 elif method=="setAccess":r["configured_access"]="unknown" if mismatch else q["mode"]
 elif method=="setPower":r["configured"]="99" if mismatch else q["dbm"]
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


    def test_wifi_mutation_response_and_acl(self):
        cases=[
          ("setWiFi2",{"action":"SET_SSID","ssid_hex":"Kantor é".encode().hex()}),
          ("setWiFi2",{"action":"SET_CHANNEL","channel":"6"}),
          ("setWiFi2",{"action":"SET_CHANNEL","channel":"0"}),
          ("setWiFi2",{"action":"SHOW_SSID"}),
          ("setWiFi2",{"action":"HIDE_SSID"}),
          ("setWiFi2",{"action":"SET_AUTH","encryption":"psk2","key_hex":"61"*8}),
          ("setWiFi2",{"action":"SET_ACCESS","macfilter":"deny","addresses":"02:00:00:00:00:01"}),
          ("set_wifi_power",{"dbm":"15","expected":"auto","confirmation":"SAVE_TXPOWER_NEXT_BOOT"})]
        for op,body in cases:
            self.assertEqual(self.call(op,body)["code"],"1",(op,body["action"] if "action" in body else "power"))
            self.assertEqual(self.call(op,body,MISMATCH="1")["code"],"-4")
        self.assertEqual(self.call("setWiFi2",{"action":"SET_SSID","ssid_hex":"00"})["code"],"-4")
        self.assertEqual(self.call("setWiFi2",{"action":"invalid"})["code"],"-4")
        self.assertEqual(self.call(cases[0][0],cases[0][1],DENY="1")["code"],"-4")
        self.assertEqual(len((self.d/"calls").read_text().splitlines()),16)
