"""Native libubox serialization with isolated switch and routing snapshots."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[2]/"rebuild/oem-updated/backend/read-only-adapter.sh"
PREFIX=os.environ.get("VECI_LIBUBOX_PREFIX","")
@unittest.skipUnless(Path(PREFIX,"bin/jshn").is_file(),"native libubox required")
class TopologyReads(unittest.TestCase):
 def test_switch_topology_and_counters(self):
  with tempfile.TemporaryDirectory() as t:
   d=Path(t);p=d/"adapter";p.write_text(P.read_text().replace("/usr/share/libubox/jshn.sh",str(Path(PREFIX,"share/libubox/jshn.sh"))))
   def cmd(n,s):
    q=d/n;q.write_text(s);q.chmod(0o700)
   cmd("ubus",'''#!/bin/sh
case "$4:$5" in
 veci.v2:ethernetPorts) printf '%s' "$PORTS";;
 veci.v2:status) echo '{"board_supported":true,"wifi_ap_enabled":true}';;
 network.interface.lan:status) echo '{"up":true}';;
 veci.v2:traffic) printf '%s' "$TRAFFIC";;
 *) exit 1;;
esac
''')
   cmd("ip",'#!/bin/sh\n[ "${FAIL_ROUTE:-0}" = 0 ] || exit 1\nprintf "%s\\n" "$ROUTES"\n')
   cmd("jsonfilter",r'''#!/usr/bin/env python3
import json,re,sys
try:
 v=json.load(sys.stdin)
 for a,b in re.findall(r'\.([a-zA-Z0-9_]+)|\[(\d+)\]',sys.argv[2]):v=v[a] if a else v[int(b)]
 if v is None:sys.exit(1)
 print(str(v).lower() if isinstance(v,bool) else v)
except (KeyError,IndexError,ValueError,TypeError):sys.exit(1)
''')
   ports=[dict(port=i,link=["up","down","unknown","up","down"][i]) for i in range(5)]
   traffic=dict(source="kernel_interface_counters",interface="usb0",rx_bytes=123,tx_bytes=456)
   env=dict(os.environ,PATH=str(d)+":"+str(Path(PREFIX,"bin"))+":"+os.environ["PATH"],LD_LIBRARY_PATH=str(Path(PREFIX,"lib")),PORTS=json.dumps(dict(available=True,ports=ports)),TRAFFIC=json.dumps(traffic),ROUTES="default dev usb0")
   def call(op,**kw):
    r=subprocess.run(["bash",str(p),op],env=env|kw,text=True,capture_output=True,timeout=6)
    self.assertTrue(r.stdout,r.stderr);return json.loads(r.stdout)
   data=call("get_port")
   self.assertEqual([x["status"] for x in data["port"]],["1","0","","1","0"])
   self.assertEqual(call("get_network_topology")["internet"],"4g")
   self.assertEqual(call("get_network_topology",ROUTES="default dev usb0\ndefault dev eth0.2")["internet"],"unknown")
   self.assertEqual(call("get_network_topology",FAIL_ROUTE="1")["code"],"-4")
   for bad in (ports[:4],ports+[ports[0]],ports[:4]+[ports[0]]):
    self.assertEqual(call("get_port",PORTS=json.dumps(dict(available=True,ports=bad)))["code"],"-4")
   self.assertEqual(call("get_wan_traffic")["data"]["rxall"],"123")
   self.assertEqual(call("get_wan_traffic",TRAFFIC=json.dumps(traffic|dict(interface="eth0.2")))["code"],"-4")
