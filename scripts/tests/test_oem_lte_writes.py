"""OEM LTE contract fixtures; mock ubus, native libubox JSON handling."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
ADAPTER=Path(__file__).resolve().parents[2]/"rebuild/oem-updated/backend/write-adapter.sh"
PREFIX=os.environ.get("VECI_LIBUBOX_PREFIX","")
@unittest.skipUnless(PREFIX and Path(PREFIX,"bin/jshn").is_file(),"native libubox required")
class LteWrites(unittest.TestCase):
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
[ "$*" = "-q get we5927_lte.main.ping_host" ] && echo 1.1.1.1
''')
        self.cmd("ubus",'''#!/usr/bin/env python3
import json,sys,os
a=sys.argv[1:]
if a[:5]==["-t","3","call","session","access"]:
 q=json.loads(a[5]);assert q["object"] in ("veci.v2.lte","veci.v2.sim")
 print(json.dumps({"access":os.getenv("DENY")!="1"}))
elif a[:3]==["-t","20","call"]:
 method=a[4];q=json.loads(a[5])
 with open(os.environ["CALLS"],"a") as f:f.write(json.dumps([method,q])+chr(10))
 mismatch=os.getenv("MISMATCH")=="1"
 r={"ok":True}
 if method=="setApn":r["configured_apn"]="wrong" if mismatch else q["apn"]
 elif method=="setFailover":r["auto_failover"]=(q["action"]=="ENABLE_FAILOVER") != mismatch
 elif method=="setMonitor":r["monitor_interval"]=999 if mismatch else int(q["interval"])
 elif method=="switchSim":r.update(configured_slot=q["slot"],selector_slot=3 if mismatch else q["slot"])
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

    def test_policy_and_sim_adapter(self):
        cases=[
          ("set_4g",{"action":"SET_APN","apn":"lab.example"},"setApn"),
          ("set_4g",{"action":"ENABLE_FAILOVER"},"setFailover"),
          ("set_4g",{"action":"DISABLE_FAILOVER"},"setFailover"),
          ("set_4g_sim",{"slot":"2","confirmation":"SWITCH_SIM_2"},"switchSim"),
          ("set_netwatchdog",{"detect_itv":"60","expected":"10","action":"lte_recovery","detect_host1":"1.1.1.1"},"setMonitor")]
        for op,body,method in cases:
            self.assertEqual(self.call(op,body)["code"],"1")
            self.assertEqual(self.call(op,body,MISMATCH="1")["code"],"-4")
        for op,body in (("set_4g",{"action":"invalid"}),("set_4g_sim",{"slot":"2","confirmation":"SWITCH_SIM_1"}),("set_netwatchdog",cases[-1][1]|{"detect_host1":"8.8.8.8"})):
            self.assertEqual(self.call(op,body)["code"],"-4")
        self.assertEqual(self.call(cases[0][0],cases[0][1],DENY="1")["code"],"-4")
        calls=[json.loads(x) for x in (self.d/"calls").read_text().splitlines()]
        self.assertEqual([x[0] for x in calls],[m for _,_,m in cases for _ in range(2)])
