"""Run existing guest captive-portal provisioner using disposable native UCI.

This is source/config acceptance only; no AP radio, netifd, dnsmasq, uspot or
firewall runtime is restarted and packet-level physical isolation is untested.
"""
import json,os,subprocess,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
GUEST=ROOT/"source/veci-app-guest/files/usr/libexec/rpcd/veci.app.guest"
MAKEFILE=ROOT/"source/veci-app-guest/Makefile"
UCI_HOST=os.environ.get("VECI_HOST_UCI") or ""
RUNTIME=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime"

class GuestNativeProvisioning(unittest.TestCase):
    def setUp(self):
        self.assertTrue(UCI_HOST and Path(UCI_HOST).is_file(),"native UCI required")
        self.temp=tempfile.TemporaryDirectory(prefix="veci-guest-native-")
        self.addCleanup(self.temp.cleanup)
        t=Path(self.temp.name)
        self.t=t; cfg=t/"etc";cfg.mkdir()
        self.cfg=cfg
        sample={
         "network":"""config interface 'lan'
  option proto 'static'
  option ipaddr '192.168.1.1'
""",
         "dhcp": "",
         "wireless": """config wifi-device 'radio0'
  option type 'mac80211'
""",
         "firewall":"""config zone 'lan'
  option name 'lan'
config zone 'wan'
  option name 'wan'
  option input 'REJECT'
  option masq '1'
""",
         "uhttpd":"""config uhttpd 'main'
  list listen_http '0.0.0.0:80'
""",
         "uspot":"",
         "veci_guest":"""config settings 'main'
  option ssid 'VeCI-Guest'
  option idle_timeout '600'
  option session_timeout '3600'
""",
        }
        for key,body in sample.items():(cfg/key).write_text(body)
        self.hostuci=t/"uci"
        self.hostuci.write_text('#!/bin/sh\nexec "$HOST_UCI" -c "$TEST_CFG" -t "$TEST_DELTA" "$@"\n')
        self.hostuci.chmod(0o700)
        self.delta=t/"delta";self.delta.mkdir()
        self.env={**os.environ,"HOST_UCI":UCI_HOST,"TEST_CFG":str(cfg),"TEST_DELTA":str(self.delta),
                  "PATH":str(t)+":"+os.environ["PATH"]}
        # Reuse the same original function bodies, not a second implementation.
        source=GUEST.read_text()
        cut=source.rfind('\ncase "$1" in\n\tlist)')
        self.assertGreater(cut,0)
        body=source[:cut]
        self.prog=t/"provision"
        body=body.replace("/etc/config/",str(cfg)+"/")
        self.prog.write_text(body+"\nprovision_portal\n")
        self.prog.chmod(0o700)
        self.preexisting=(cfg/"firewall").read_bytes()
    def uci(self, name):
        p=subprocess.run([str(self.hostuci),"-q","get",name],env=self.env,
                         text=True,capture_output=True,timeout=6)
        return p.stdout.strip() if p.returncode==0 else None

    def test_real_guest_provisioning_is_disabled_and_no_lan_forward(self):
        result=subprocess.run(["sh",str(self.prog)],env=self.env,capture_output=True,text=True,timeout=16)
        self.assertEqual(result.returncode,0,result.stderr+"\n"+result.stdout)
        self.assertEqual(self.uci("network.veci_guest.ipaddr"),"10.20.0.1")
        self.assertEqual(self.uci("network.veci_guest.netmask"),"255.255.255.0")
        self.assertEqual(self.uci("dhcp.veci_guest.interface"),"veci_guest")
        self.assertEqual(self.uci("dhcp.veci_guest.start"),"100")
        self.assertEqual(self.uci("dhcp.veci_guest.limit"),"100")
        self.assertEqual(self.uci("wireless.veci_guest.disabled"),"1")
        self.assertEqual(self.uci("wireless.veci_guest.device"),"radio0")
        self.assertEqual(self.uci("wireless.veci_guest.network"),"veci_guest")
        self.assertEqual(self.uci("firewall.veci_guest_zone.input"),"REJECT")
        self.assertEqual(self.uci("firewall.veci_guest_zone.forward"),"REJECT")
        self.assertEqual(self.uci("firewall.veci_guest_forward.dest"),"wan")
        self.assertEqual(self.uci("firewall.veci_guest_forward.ipset"),"uspot")
        self.assertEqual(self.uci("firewall.veci_guest_forward.target"),"ACCEPT")
        self.assertIsNone(self.uci("firewall.veci_guest_to_lan"))
        self.assertEqual(self.uci("firewall.wan.input"),"REJECT")
        self.assertEqual(self.uci("wireless.radio0"),"wifi-device")
        self.assertEqual(self.uci("uhttpd.main.listen_http"),"192.168.1.1:80")
        self.assertEqual(self.uci("uhttpd.veci_guest.enabled"),"0")
        # No command that starts a live guest network in the provisioning path.
        self.assertNotIn("service_restart",self.prog.read_text().split("provision_base() {")[1].split("\n}\n")[0])

    def test_source_has_fail_closed_guest_rollback_and_packet_scope(self):
        source=GUEST.read_text()
        for marker in ("portal_snapshot_begin","portal_snapshot_restore",
            "guest_save_failed_rolled_back","set firewall.veci_guest_zone.input='REJECT'",
            "set firewall.veci_guest_zone.forward='REJECT'",
            "set firewall.veci_guest_forward.ipset='uspot'",
            "set wireless.veci_guest.disabled='1'",
            "set wireless.veci_guest.network='veci_guest'"):
            self.assertIn(marker,source)
        self.assertNotIn("set firewall.veci_guest_zone.forward='ACCEPT'",source)
        self.assertIn("+uspot +uspot-www",MAKEFILE.read_text())
        self.assertIn("guest_isolation_verified", (RUNTIME/"veci2-guest-check").read_text())
        self.assertIn('"guest_isolation_verified":null', (RUNTIME/"veci2-guest-check").read_text())
        subprocess.run(["busybox","ash","-n",str(GUEST)],check=True,capture_output=True)

if __name__=="__main__":unittest.main()
