"""Offline home aggregator concurrency and fallback regression."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[2]/"rebuild/oem-updated/backend/home-adapter.sh"
class HomeParallel(unittest.TestCase):
 def test_parallel_pairs_and_partial_failure(self):
  with tempfile.TemporaryDirectory() as t:
   d=Path(t);p=d/"home";p.write_text(P.read_text().replace("/var/lock/oem-home.lock",str(d/"lock")).replace("/usr/libexec/oem-updated/read-only-adapter",str(d/"adapter")))
   def cmd(n,s):
    x=d/n;x.write_text(s);x.chmod(0o700)
   cmd("adapter",'''#!/usr/bin/env python3
import fcntl,json,os,sys,time
from pathlib import Path
p=Path(os.environ["STATE"])
def update(delta):
 with p.open("r+") as f:
  fcntl.flock(f,fcntl.LOCK_EX);a=json.load(f);a["active"]+=delta;a["peak"]=max(a["peak"],a["active"]);f.seek(0);json.dump(a,f);f.truncate()
update(1);time.sleep(.25);update(-1)
if sys.argv[1]=="get_system_status":sys.exit(1)
print(json.dumps(dict(code="1",operation=sys.argv[1])))
''')
   cmd("jsonfilter",'#!/usr/bin/env python3\nimport json,sys;print(json.load(sys.stdin)["code"])\n')
   state=d/"state";state.write_text('{"active":0,"peak":0}')
   r=subprocess.run(["sh",str(p)],env=dict(os.environ,PATH=str(d)+":"+os.environ["PATH"],STATE=str(state)),text=True,capture_output=True,timeout=12)
   self.assertEqual(r.returncode,0,r.stderr);data=json.loads(r.stdout)["home"]
   self.assertEqual(json.loads(state.read_text()),{"active":0,"peak":2})
   self.assertEqual(data["get_system_status"]["code"],"-4")
   self.assertEqual(data["get_system_status"]["cpu_usage"],"")
   self.assertEqual(data["get_wan_traffic"]["operation"],"app_home")
   self.assertFalse(data["getWiFi5"]["supported"])
   self.assertEqual(len(data),9)
