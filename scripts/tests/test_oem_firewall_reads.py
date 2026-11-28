"""Scoped native ACL and TTL read contracts with libubox."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[2]/"rebuild/oem-updated/backend/read-only-adapter.sh"
PREFIX=os.environ.get("VECI_LIBUBOX_PREFIX","")
@unittest.skipUnless(Path(PREFIX,"bin/jshn").is_file(),"native libubox required")
class FirewallReads(unittest.TestCase):
 def test_acl_and_ttl(self):
  with tempfile.TemporaryDirectory() as t:
   d=Path(t);p=d/"adapter";p.write_text(P.read_text().replace("/usr/share/libubox/jshn.sh",str(Path(PREFIX,"share/libubox/jshn.sh"))).replace("/proc/sys/net/ipv4/ip_default_ttl",str(d/"ttl")))
   (d/"ttl").write_text("64\n")
   def cmd(n,s):
    q=d/n;q.write_text(s);q.chmod(0o700)
   cmd("ubus",'''#!/bin/sh
case "$4:$5" in
 veci.v2.firewall:aclStatus) printf '%s' "$RULES";;
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
   rows=[dict(slot="1",mac="02:00:00:00:00:01",enabled="1"),dict(slot="4",mac="02:00:00:00:00:04",enabled="0")]
   rules=dict(ok=True,revision="a"*64,rules=rows)
   ttl=dict(ok=True,enabled="1",ttl="64",revision="b"*64,runtime="rule_present")
   env=dict(os.environ,PATH=str(d)+":"+str(Path(PREFIX,"bin"))+":"+os.environ["PATH"],LD_LIBRARY_PATH=str(Path(PREFIX,"lib")),RULES=json.dumps(rules),TTL=json.dumps(ttl))
   def call(op,**kw):
    r=subprocess.run(["bash",str(p),op],env=env|kw,text=True,capture_output=True,timeout=6)
    self.assertTrue(r.stdout,r.stderr);return json.loads(r.stdout)
   for op in ("get_acl_rule","get_acl_status"):
    data=call(op);self.assertEqual(data["code"],"1")
    self.assertEqual([x["slot"] for x in data["data"]],["1","4"])
    self.assertEqual(data["enabled_count"],1)
    self.assertEqual(data["data"][0]["editable"],"1")
    for bad in (rows+[rows[0]], [rows[0]|dict(mac="bad")], [rows[0]|dict(enabled="9")]):
     self.assertEqual(call(op,RULES=json.dumps(rules|dict(rules=bad)))["code"],"-4")
   self.assertEqual(call("get_ttl")["ttl_cnt"],"64")
   self.assertEqual(call("get_ttl",TTL=json.dumps(ttl|dict(enabled="0",ttl="64")))["ttl_cnt"],"")
   self.assertEqual(call("get_ttl",TTL=json.dumps(ttl|dict(ttl="256")))["code"],"-4")
