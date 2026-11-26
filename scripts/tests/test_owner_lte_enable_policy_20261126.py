#!/usr/bin/env python3
"""Exercise the exact LTE policy with temporary UCI/manager mocks; never touch hardware."""
from pathlib import Path
import json,os,subprocess,tempfile,unittest

ROOT=Path(__file__).resolve().parents[2]
BACKEND=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime/veci2-lte-policy"
class TestEnableConnection(unittest.TestCase):
 def test_enable_is_explicit_board_locked_and_never_restarts_router(self):
  with tempfile.TemporaryDirectory(prefix="veci-enable-test-") as temp:
   d=Path(temp)
   board=d/"board";board.write_text("zbtlink,zbt-we5927\n")
   state=d/"state.json";state.write_text(json.dumps({
     "we5927_lte.main":"modem","we5927_lte.main.enabled":"0",
     "we5927_lte.main.apn":"internet","we5927_lte.main.auto_failover":"0",
     "we5927_lte.main.ping_interval":"10","we5927_lte.main.sim":"1"
   }))
   log=d/"manager.log"
   mgr=d/"lte-manager";mgr.write_text("#!/bin/sh\nprintf '%s\\n' \"$1\" >>\"$FAKE_MANAGER_LOG\"\n");mgr.chmod(0o700)
   lte=d/"we5927-lte";lte.write_text("#!/bin/sh\ncase \"$1\" in validate-apn) exit 0;; selector-slot) echo 1;; *) exit 9;; esac\n");lte.chmod(0o700)
   uci=d/"uci";uci.write_text("""#!/usr/bin/env python3
import json,os,sys
p=os.environ["FAKE_UCI_STATE"];data=json.load(open(p));a=sys.argv[1:]
if a and a[0]=="-q":a.pop(0)
if a and a[0]=="-t":a=a[2:]
op=a.pop(0)
if op=="get":
 v=data.get(a[0])
 if v is None:sys.exit(1)
 print(v)
elif op=="changes":pass
elif op=="set":
 k,v=a[0].split("=",1);data[k]=v;open(p,"w").write(json.dumps(data))
elif op=="commit":pass
else:sys.exit(2)
""");uci.chmod(0o700)
   jf=d/"jsonfilter";jf.write_text("""#!/usr/bin/env python3
import json,sys
a=sys.argv[1:];raw=a[a.index("-s")+1];key=a[a.index("-e")+1][2:];v=json.loads(raw).get(key)
if v is None:sys.exit(1)
print(v)
""");jf.chmod(0o700)
   text=BACKEND.read_text().replace("/tmp/sysinfo/board_name",str(board))
   text=text.replace("/usr/sbin/we5927-lte",str(lte))
   text=text.replace("/etc/init.d/we5927-lte",str(mgr))
   exe=d/"provider";exe.write_text(text)
   env=dict(os.environ, PATH=str(d)+":"+os.environ["PATH"],FAKE_UCI_STATE=str(state),FAKE_MANAGER_LOG=str(log))
   def run(method,req=""):
    r=subprocess.run(["busybox","ash",str(exe),"call",method],input=req,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,timeout=8)
    self.assertEqual(r.returncode,0,r.stderr)
    return json.loads(r.stdout)
   start=run("status")
   self.assertFalse(start["connection_enabled"]);self.assertFalse(start["activation_requested"])
   invalid=run("enableConnection",'{"action":"OFF"}')
   self.assertEqual(invalid,{"ok":False,"error":"invalid_action"})
   self.assertEqual(json.loads(state.read_text())["we5927_lte.main.enabled"],"0")
   self.assertFalse(log.exists())
   result=run("enableConnection",'{"action":"ENABLE_CONNECTION"}')
   self.assertTrue(result["connection_enabled"])
   self.assertTrue(result["activation_requested"])
   self.assertEqual(log.read_text().splitlines(),["enable","start"])
   updated=json.loads(state.read_text())
   self.assertEqual(updated["we5927_lte.main.enabled"],"1")
   self.assertEqual(updated["we5927_lte.main.apn"],"internet")
   self.assertEqual(updated["we5927_lte.main.auto_failover"],"0")
   again=run("status")
   self.assertTrue(again["connection_enabled"]);self.assertFalse(again["activation_requested"])
   self.assertEqual(len(log.read_text().splitlines()),2)

if __name__=="__main__":unittest.main()
