"""OEM NTP and cron contract fixtures; mock ubus, native libubox JSON handling."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
ADAPTER=Path(__file__).resolve().parents[2]/"rebuild/oem-updated/backend/write-adapter.sh"
PREFIX=os.environ.get("VECI_LIBUBOX_PREFIX","")
@unittest.skipUnless(PREFIX and Path(PREFIX,"bin/jshn").is_file(),"native libubox required")
class SystemWrites(unittest.TestCase):
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
case "$3" in
 system.ntp.enable_server) echo 0;;
 'system.@system[0].timezone') echo UTC0;;
 *) exit 1;;
esac
''')
        self.cmd("ubus",'''#!/usr/bin/env python3
import json,sys,os
a=sys.argv[1:]
if a[:5]==["-t","3","call","session","access"]:
 q=json.loads(a[5]);assert q["object"] in ("veci.v2.system","veci.v2.cron")
 print(json.dumps({"access":os.getenv("DENY")!="1"}))
elif a[:3]==["-t","20","call"]:
 method=a[4];q=json.loads(a[5]);bad=os.getenv("MISMATCH")=="1"
 with open(os.environ["CALLS"],"a") as f:f.write(json.dumps([method,q])+chr(10))
 if method=="setNtp":r={"ok":True,"enabled":"1","servers":["wrong" if bad else q["first"]]+([q["second"]] if q["second"] else [])}
 elif method=="setReboot":r=dict(q,ok=True,hour="99" if bad else q["hour"])
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


    def test_ntp_and_disabled_schedule_receipts(self):
        ntp=dict(server_primary="0.pool.ntp.org",server_secondary="1.pool.ntp.org",enable_ntp_client="1",enable_ntp_server="0",timezone="UTC0")
        cron=dict(revision="a"*64,enabled="0",hour="4",minute="15",weekdays="1,3,5",confirmation="DISABLE_SCHEDULED_REBOOT")
        for op,body in (("set_ntp",ntp),("setAutoreboot",cron)):
            self.assertEqual(self.call(op,body)["code"],"1")
            self.assertEqual(self.call(op,body,MISMATCH="1")["code"],"-4")
            self.assertEqual(self.call(op,body,DENY="1")["code"],"-4")
        self.assertEqual(self.call("set_ntp",ntp|{"timezone":"other"})["code"],"-4")
        self.assertEqual(self.call("setAutoreboot",cron|{"confirmation":"wrong"})["code"],"-4")
        self.assertEqual(len((self.d/"calls").read_text().splitlines()),4)
