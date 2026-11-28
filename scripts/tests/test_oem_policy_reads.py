"""Native policy and route read contracts with libubox."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[2]/"rebuild/oem-updated/backend/read-only-adapter.sh"
PREFIX=os.environ.get("VECI_LIBUBOX_PREFIX","")
@unittest.skipUnless(Path(PREFIX,"bin/jshn").is_file(),"native libubox required")
class PolicyReads(unittest.TestCase):
 def test_policy_and_route(self):
  with tempfile.TemporaryDirectory() as t:
   d=Path(t);p=d/"adapter";p.write_text(P.read_text().replace("/usr/share/libubox/jshn.sh",str(Path(PREFIX,"share/libubox/jshn.sh"))).replace("/proc/sys/net/ipv4/ip_default_ttl",str(d/"ttl")))
   (d/"ttl").write_text("64\n")
   def cmd(n,s):
    q=d/n;q.write_text(s);q.chmod(0o700)
   cmd("ubus",'''#!/bin/sh
case "$4:$5" in
 veci.v2.firewall:parentStatus) printf '%s' "$RULES";;
 veci.v2.firewall:status) printf '%s' "$FW";;
 veci.v2.routes:status) printf '%s' "$ROUTE";;
 veci.v2.firewall:ttlStatus) printf '%s' "$TTL";;
 *) exit 1;;
esac
''')
   cmd("jsonfilter",r'''#!/usr/bin/env python3
import json,re,sys
try:
 v=json.load(sys.stdin)
 for a,b in re.findall(r'\.([a-zA-Z0-9_]+)|\[(\d+)\]',sys.argv[2]):v=v[a] if a else v[int(b)]
 if v is None:sys.exit(1)
 print(str(v).lower() if isinstance(v,bool) else v)
except (KeyError,IndexError,ValueError,TypeError):sys.exit(1)
''')
   cmd("uci",'#!/bin/sh\ncase "$2" in show) echo network.wan=interface;; get) exit 1;; esac\n')
   rows=[dict(slot="1",mac="02:00:00:00:00:01",enabled="1",start_time="08:00:00",stop_time="09:00:00",weekdays="Monday Friday",timezone="UTC")]
   rules=dict(ok=True,revision="a"*64,rules=rows)
   fw=dict(ok=True,revision="a"*64,flow_offloading="1",flow_offloading_hw="0")
   route=dict(ok=True,revision="a"*64,entries=[dict(section="veci2_route_test",kind="route",target="192.0.2.0/24",interface="wan",gateway="192.0.2.1",table="254",editable=True)])
   env=dict(os.environ,PATH=str(d)+":"+str(Path(PREFIX,"bin"))+":"+os.environ["PATH"],LD_LIBRARY_PATH=str(Path(PREFIX,"lib")),RULES=json.dumps(rules),FW=json.dumps(fw),ROUTE=json.dumps(route))
   def call(op,**kw):
    r=subprocess.run(["bash",str(p),op],env=env|kw,text=True,capture_output=True,timeout=6)
    self.assertTrue(r.stdout,r.stderr);return json.loads(r.stdout)
   for op in ("get_parents_ctrl_rule","get_parents_ctrl_status"):
    data=call(op);self.assertEqual(data["code"],"1",data)
    self.assertEqual(data["data"][0]["weekdays"],"Monday Friday")
    self.assertEqual(data["enabled_count"],1)
    for bad in (rows+rows,[rows[0]|dict(timezone="local")],[rows[0]|dict(enabled="9")]):
     self.assertEqual(call(op,RULES=json.dumps(rules|dict(rules=bad)))["code"],"-4")
   data=call("get_nat_acceleration")["data"]
   self.assertEqual(data["status"],"1");self.assertEqual(data["hardware_configured"],"0")
   self.assertEqual(call("get_nat_acceleration",FW=json.dumps(fw|dict(flow_offloading_hw="9")))["code"],"-4")
   data=call("get_static_route")
   self.assertEqual(data["data"][0]["netmask"],"255.255.255.0")
   for prefix,mask in (("0","0.0.0.0"),("17","255.255.128.0"),("32","255.255.255.255")):
    item=route["entries"][0]|dict(target="192.0.2.0/"+prefix)
    self.assertEqual(call("get_static_route",ROUTE=json.dumps(route|dict(entries=[item])))["data"][0]["netmask"],mask)
