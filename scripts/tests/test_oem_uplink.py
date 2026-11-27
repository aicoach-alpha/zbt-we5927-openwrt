"""Native STA read and topology rejection using isolated dependencies."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SOURCE=Path(__file__).resolve().parents[2]/"rebuild/veci-v2/packages/veci-v2-runtime/veci2-wifi"

class Uplink(unittest.TestCase):
    def test_topology_read_and_denial(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            for file,value in (("board","zbtlink,zbt-we5927"),("wireless","wireless"),("network","network"),("firewall","firewall")):
                (d/file).write_text(value+"\n")
            (d/"jshn").write_text("""
json_init() { :; }
json_add_boolean() { printf '%s=%s\\n' "$1" "$2"; }
json_add_string() { printf '%s=%s\\n' "$1" "$2"; }
json_dump() { :; }
""")
            s=SOURCE.read_text()
            for old,new in (("/tmp/sysinfo/board_name","board"),("/etc/config/wireless","wireless"),("/etc/config/network","network"),("/etc/config/firewall","firewall"),("/usr/share/libubox/jshn.sh","jshn"),("/var/lock/veci2-ipv6.lock","lock")):
                s=s.replace(old,str(d/new))
            s=s.replace("/etc/config/$cfg",str(d)+"/$cfg").replace("/usr/libexec/rpcd/veci.v2.firewall",str(d/"fw-rpc"))
            (d/"fw-rpc").touch()
            (d/"rpc").write_text(s)
            uci=d/"uci"
            uci.write_text("""#!/bin/sh
case "$2" in
 changes) exit 0;;
 show) [ "$3" = wireless ] || exit 1; [ -z "${FOREIGN:-}" ] || echo "wireless.other.mode='sta'"; exit 0;;
 get) ;;
 *) echo MUTATION_ATTEMPT >&2; exit 99;;
esac
case "$3" in
 wireless.default_radio0) echo wifi-iface;;
 wireless.default_radio0.device) echo radio0;;
 wireless.default_radio0.mode) echo ap;;
 wireless.radio0) echo wifi-device;;
 wireless.radio0.band) echo 2g;;
 network.wwan) echo interface;;
 network.wwan.proto) echo dhcp;;
 'firewall.@zone[1].name') echo wan;;
 'firewall.@zone[1].input') echo REJECT;;
 'firewall.@zone[1].network') echo "${WAN:-wan lte wwan}";;
 'firewall.@zone[0].network') echo lan;;
 *) exit 1;;
esac
""")
            uci.chmod(0o755)
            def run(method,**env):
                return subprocess.run(["sh",str(d/"rpc"),"call",method],input="{}",text=True,capture_output=True,timeout=5,env=dict(os.environ,PATH=str(d)+":"+os.environ["PATH"],**env))
            r=run("uplinkStatus")
            self.assertEqual(r.returncode,0,r.stderr)
            for value in ("eligible=1","configured=0","enabled=0","connection_verified=0"):
                self.assertIn(value,r.stdout)
            for env in ({"WAN":"wan lte"},{"FOREIGN":"1"}):
                self.assertIn("eligible=0",run("uplinkStatus",**env).stdout)
                r=run("saveUplink",**env)
                self.assertIn("wwan_topology_unavailable",r.stdout)
                self.assertNotIn("MUTATION_ATTEMPT",r.stderr)
