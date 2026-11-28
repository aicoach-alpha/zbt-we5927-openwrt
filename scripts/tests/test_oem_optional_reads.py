"""Native JSON serialization of optional service status, without live services."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[2]/"rebuild/oem-updated/backend/read-only-adapter.sh"
PREFIX=os.environ.get("VECI_LIBUBOX_PREFIX","")
@unittest.skipUnless(Path(PREFIX,"bin/jshn").is_file(),"native libubox required")
class OptionalReads(unittest.TestCase):
 def test_status_contracts(self):
  with tempfile.TemporaryDirectory() as t:
   d=Path(t);p=d/"adapter";p.write_text(P.read_text().replace("/usr/share/libubox/jshn.sh",str(Path(PREFIX,"share/libubox/jshn.sh"))))
   def cmd(n,s):
    q=d/n;q.write_text(s);q.chmod(0o700)
   cmd("ubus",'''#!/bin/sh
case "$4:$5" in
 veci.v2.addon:ddnsStatus|veci.v2.addon:sqmStatus) printf '%s' "$PROFILE";;
 service:list) printf '%s' "$SERVICE";;
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
   env=dict(os.environ,PATH=str(d)+":"+str(Path(PREFIX,"bin"))+":"+os.environ["PATH"],LD_LIBRARY_PATH=str(Path(PREFIX,"lib")))
   def call(op,**kw):
    r=subprocess.run(["bash",str(p),op],env=env|kw,text=True,capture_output=True,timeout=6)
    self.assertTrue(r.stdout,r.stderr);return json.loads(r.stdout)
   for svc,ops in (("ddns",("get_ddns","get_ddns_stat")),("sqm",("get_qos","get_qos_status"))):
    for op in ops:
     for state,flag in (("absent","0"),("unconfigured","0"),("disabled","0"),("enabled","1")):
      profile=dict(ok=True,service=svc,state=state,enabled=flag,revision="a"*64,password="fixture-secret",interface="usb0",download="10000",upload="2000",qdisc="cake",script="piece_of_cake.qos")
      data=call(op,PROFILE=json.dumps(profile))
      self.assertEqual(data["code"],"1",data);self.assertEqual(data["state"],state)
      self.assertNotIn("fixture-secret",json.dumps(data))
      if svc=="sqm":self.assertEqual(len(data["data"]),int(state in ("disabled","enabled")))
      self.assertEqual(call(op,PROFILE=json.dumps(profile|dict(enabled=str(1-int(flag)))))["code"],"-4")
      self.assertEqual(call(op,PROFILE=json.dumps(profile|dict(service="other")))["code"],"-4")
   for inv,flag in (({},"0"),({"openvpn":{"instances":{"lab":{"running":True}}}},"1"),({"openvpn":{"instances":{"lab":{"running":False}}}},"0")):
    data=call("get_openvpn_status",SERVICE=json.dumps(inv));self.assertEqual(data["openvpn_status"],flag);self.assertEqual(data["tunnel_verified"],"false")
   self.assertEqual(call("get_openvpn_status",SERVICE='{"openvpn":3}')["code"],"-4")
