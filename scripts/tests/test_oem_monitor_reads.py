"""Isolated kernel status and down-interface fixtures, no live router."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[2]/"rebuild/oem-updated/backend/read-only-adapter.sh"
PREFIX=os.environ.get("VECI_LIBUBOX_PREFIX","")
@unittest.skipUnless(Path(PREFIX,"bin/jshn").is_file(),"native libubox required")
class MonitorReads(unittest.TestCase):
 def test_down_interfaces_cpu_and_disk(self):
  with tempfile.TemporaryDirectory() as t:
   d=Path(t);p=d/"adapter";s=P.read_text().replace("/usr/share/libubox/jshn.sh",str(Path(PREFIX,"share/libubox/jshn.sh")))
   for f,data in (("uptime","100.00 50.00\n"),("loadavg","0.10 0.20 0.30 1/10 1\n"),("meminfo","MemTotal: 64000 kB\nMemAvailable: 32000 kB\n"),("stat","cpu 100 0 100 800 0 0 0 0\n"),("mounts","overlay /overlay jffs2 rw 0 0\ntmpfs /tmp tmpfs rw 0 0\n")):
    (d/f).write_text(data);s=s.replace("/proc/"+f,str(d/f))
   s=s.replace("/sys/class/net/",str(d/"net")+"/");p.write_text(s)
   def cmd(n,s):
    q=d/n;q.write_text(s);q.chmod(0o700)
   cmd("ubus",'''#!/bin/sh
case "$4:$5" in
 network.interface.*:status) printf '%s' "$LIVE";;
 veci.v2.wifi:info) echo '{"ok":true,"clients":[]}';;
 *) exit 1;;
esac
''')
   cmd("jsonfilter",r'''#!/usr/bin/env python3
import json,re,sys
try:
 v=json.load(sys.stdin)
 for a,b,c in re.findall(r'\.([a-zA-Z0-9_]+)|\["([^"]+)"\]|\[(\d+)\]',sys.argv[2]):v=v[a or b] if a or b else v[int(c)]
 if isinstance(v,list):print("\n".join(map(str,v)))
 elif v is not None:print(str(v).lower() if isinstance(v,bool) else v)
except (KeyError,IndexError,ValueError,TypeError):sys.exit(1)
''')
   cmd("sleep",f'#!/bin/sh\necho "cpu 110 0 110 880 0 0 0 0" > "{d}/stat"\n')
   cmd("df",'#!/bin/sh\necho "Filesystem 1024-blocks Used Available Capacity Mounted on"\necho "fixture 1000 300 700 30% $2"\n')
   env=dict(os.environ,PATH=str(d)+":"+str(Path(PREFIX,"bin"))+":"+os.environ["PATH"],LD_LIBRARY_PATH=str(Path(PREFIX,"lib")),LIVE=json.dumps(dict(up=False,proto="pppoe",**{"ipv4-address":[{"address":"192.0.2.10"}]})))
   def call(op,**kw):
    r=subprocess.run(["bash",str(p),op],env=env|kw,text=True,capture_output=True,timeout=6)
    self.assertTrue(r.stdout,r.stderr);return json.loads(r.stdout)
   for op in ("get_lan_status","get_wan_status"):
    data=call(op)["data"];self.assertEqual(data["ipaddr"],"");self.assertEqual(data["link_state"],"false");self.assertEqual(data["rx"],"")
    self.assertEqual(call(op,LIVE=json.dumps(dict(up=True,proto="dhcp")))["code"],"-4")
   data=call("get_system_status");self.assertEqual(data["cpu_usage"],"20");self.assertEqual(data["memory_usage"],"50");self.assertEqual(data["online_user_num"],"0")
   data=call("get_disk");self.assertEqual([r["disk_type"] for r in data["data"]],["jffs2","tmpfs"])
   (d/"mounts").write_text("tmpfs /tmp tmpfs rw 0 0\n")
   self.assertEqual(call("get_disk")["code"],"-4")
