"""Offline bounded diagnostic command and native survey contract tests."""
import fcntl,json,os,subprocess,tempfile,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[2]/"rebuild/oem-updated/backend/diagnostics-adapter.sh"
PREFIX=os.environ.get("VECI_LIBUBOX_PREFIX","")
@unittest.skipUnless(Path(PREFIX,"bin/jshn").is_file(),"native libubox required")
class Diagnostics(unittest.TestCase):
 def test_commands_and_guards(self):
  with tempfile.TemporaryDirectory() as t:
   d=Path(t);lock=d/"lock";p=d/"provider"
   p.write_text(P.read_text().replace("/var/lock/oem-diagnostics.lock",str(lock)).replace("/usr/share/libubox/jshn.sh",str(Path(PREFIX,"share/libubox/jshn.sh"))))
   def cmd(name,code):
    x=d/name;x.write_text(code);x.chmod(0o700)
   for name in ("ping","ping6","traceroute","traceroute6","nslookup"):
    cmd(name,'#!/bin/sh\nprintf "%s %s\\n" "${0##*/}" "$*"\nexit "${RC:-0}"\n')
   cmd("timeout",'#!/bin/sh\nshift\nexec "$@"\n')
   cmd("ubus",'''#!/bin/sh
case "$*" in
 *"session access"*) printf '{"access":%s}' "${ALLOW:-true}";;
 *"wifi survey"*) printf '%s' "$SURVEY";;
 *) exit 99;;
esac
''')
   cmd("jsonfilter",r'''#!/usr/bin/env python3
import json,re,sys
try:
 v=json.load(sys.stdin)
 for a,b in re.findall(r'\.([a-zA-Z0-9_]+)|\[(\d+)\]',sys.argv[2]):v=v[a] if a else v[int(b)]
 print(str(v).lower() if isinstance(v,bool) else v)
except (KeyError,IndexError,ValueError):sys.exit(1)
''')
   env=dict(os.environ,PATH=str(d)+":"+str(Path(PREFIX,"bin"))+":"+os.environ["PATH"],LD_LIBRARY_PATH=str(Path(PREFIX,"lib")))
   def call(op,host="example.test",version="4",**kw):
    x=subprocess.run(["bash",str(p),op,host,version,"a"*32],env=env|kw,text=True,capture_output=True,timeout=5)
    self.assertEqual(x.returncode,0,x.stderr);return json.loads(x.stdout)
   for op,ver,expected in (("test_ping","4","ping -c 4 -W 2"),("test_ping","6","ping6 -c 4 -W 2"),("test_traceroute","4","traceroute -m 5 -q 1 -w 2"),("test_traceroute","6","traceroute6 -m 5 -q 1 -w 2"),("test_nslookup","4","nslookup")):
    result=call(op,version=ver)
    self.assertEqual(result["code"],"1");self.assertIn(expected,result["data"])
    self.assertEqual(call(op,version=ver,RC="1")["exit_code"],1)
   for host in ("-h","https://example.test","a;reboot","a b","x"*254):
    self.assertEqual(call("test_ping",host)["code"],"-4")
   with lock.open("w") as f:
    fcntl.flock(f,fcntl.LOCK_EX)
    self.assertEqual(call("test_ping")["reason"],"diagnostic busy")
   row=dict(bssid="02:11:22:33:44:55",frequency_mhz=2412,ssid="lab",signal_dbm=-50)
   result=call("site_survey",SURVEY=json.dumps(dict(ok=True,networks=[row])))
   self.assertEqual(result["data"][0]["channel"],"1")
   self.assertEqual(call("site_survey",ALLOW="false")["code"],"-4")
   for patch in (dict(bssid="bad"),dict(frequency_mhz=5200)):
    self.assertEqual(call("site_survey",SURVEY=json.dumps(dict(ok=True,networks=[row|patch])))["code"],"-4")
