"""Disposable native UCI integration. No real Wi-Fi, firewall, or network service."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

R=Path(__file__).resolve().parents[2]/"rebuild/veci-v2/packages/veci-v2-runtime"
UCI=os.environ.get("VECI_HOST_UCI","")

@unittest.skipUnless(UCI and Path(UCI).is_file(),"native host UCI required")
class NativeGuest(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d=Path(tmp.name)
        self.cfg=self.d/"config";self.cfg.mkdir()
        self.delta=self.d/"delta";self.delta.mkdir()
        configs={
            "network":"config interface 'lan'\n option proto 'static'\n option ipaddr '192.168.1.1'\n option netmask '255.255.255.0'\n",
            "wireless":"config wifi-device 'radio0'\n option band '2g'\nconfig wifi-iface 'default_radio0'\n option mode 'ap'\n option network 'lan'\n",
            "dhcp":"config dnsmasq\n option domainneeded '1'\n",
            "firewall":"config defaults\n option forward 'REJECT'\nconfig zone\n option name 'lan'\n option network 'lan'\nconfig zone\n option name 'wan'\n option input 'REJECT'\n option masq '1'\n",
        }
        for c,s in configs.items():(self.cfg/c).write_text(s)
        self.original={x.name:x.read_bytes() for x in self.cfg.iterdir()}
        (self.d/"board").write_text("zbtlink,zbt-we5927\n")
        for x in ("wifi-rpc","fw-rpc"):(self.d/x).touch()
        self.cmd("uci",'#!/bin/sh\nexec "$HOST_UCI" -c "$TEST_CFG" -t "$TEST_DELTA" "$@"\n')
        self.cmd("ip",'#!/bin/sh\n[ "$*" = "-4 route show table all" ] || exit 99\nprintf "%s\\n" "${ROUTES:-192.168.1.0/24 dev br-lan}"\n')
        self.cmd("fw4",'#!/bin/sh\n[ "$*" = check ] || exit 99\n[ "${FAIL_FW:-0}" = 0 ]\n')
        (self.d/"jshn").write_text("""
json_init() { :; }
json_load() { [ -n "$1" ]; }
json_get_var() {
  case "$2" in revision) v="$REVISION";; confirmation) v="$CONFIRM";; ssid) v="Guest Lab";; password) v="LabOnly1234";; enabled) v="$ENABLED";; *) return 1;; esac
  export "$1=$v"
}
json_add_boolean() { printf '%s=%s\\n' "$1" "$2"; }
json_add_string() { printf '%s=%s\\n' "$1" "$2"; }
json_add_null() { printf '%s=null\\n' "$1"; }
json_dump() { :; }
""")
        s=(R/"veci2-guest-check").read_text()
        for old,new in (("/etc/config/","config/"),("/tmp/sysinfo/board_name","board"),("/usr/libexec/rpcd/veci.v2.wifi","wifi-rpc"),("/usr/libexec/rpcd/veci.v2.firewall","fw-rpc"),("/usr/libexec/rpcd/veci.app.guest","legacy-app"),("/usr/share/libubox/jshn.sh","jshn"),("/var/lock/veci2-ipv6.lock","network.lock"),("/var/lock/veci2-dhcp.lock","dhcp.lock"),("/var/run/veci2-reboot-requested","reboot-pending")):
            s=s.replace(old,str(self.d)+"/"+new)
        (self.d/"rpc").write_text(s)
        self.env=dict(os.environ,HOST_UCI=UCI,TEST_CFG=str(self.cfg),TEST_DELTA=str(self.delta),PATH=str(self.d)+":"+os.environ["PATH"])
    def cmd(self,name,source):
        p=self.d/name;p.write_text(source);p.chmod(0o700)
    def call(self,method,**env):
        return subprocess.run(["sh",str(self.d/"rpc"),"call",method],input="{}",text=True,capture_output=True,timeout=15,env=dict(self.env,REVISION="",CONFIRM="",ENABLED="0")|env)
    def revision(self):
        r=self.call("status")
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn("ok=1",r.stdout,r.stderr)
        return next(x.split("=",1)[1] for x in r.stdout.splitlines() if x.startswith("revision="))
    def uci(self,*args):
        r=subprocess.run(["uci","-q",*args],env=self.env,text=True,capture_output=True,timeout=5)
        return r.stdout.strip() if r.returncode==0 else None
    def provision(self,**env):
        args=dict(REVISION=self.revision(),CONFIRM="PROVISION_GUEST_DISABLED");args.update(env)
        return self.call("provisionNative",**args)
    def test_provision_and_toggle_with_native_uci(self):
        self.assertIn("native_eligible=1",self.call("status").stdout)
        r=self.provision()
        self.assertIn("configured=1",r.stdout,r.stderr)
        self.assertIn("enabled_configured=0",r.stdout,r.stderr)
        self.assertNotIn("LabOnly1234",r.stdout)
        for k,v in {"wireless.veci_guest.disabled":"1","wireless.veci_guest.isolate":"1","wireless.veci_guest.encryption":"psk2","network.veci_guest.ipaddr":"10.20.0.1","dhcp.veci_guest.ra":"disabled","firewall.veci_guest_zone.forward":"REJECT","firewall.veci_guest_internet.dest":"wan","firewall.veci_guest_internet.family":"ipv4"}.items():
            self.assertEqual(self.uci("get",k),v,k)
        self.assertIsNone(self.uci("get","firewall.veci_guest_to_lan"))
        rev=self.revision()
        self.assertIn("enabled_configured=1",self.call("setNativeStartup",REVISION=rev,CONFIRM="ENABLE_NATIVE_GUEST_NEXT_BOOT",ENABLED="1").stdout)
        self.assertEqual(self.uci("get","wireless.veci_guest.disabled"),"0")
        self.assertIn("enabled_configured=0",self.call("setNativeStartup",REVISION=self.revision(),CONFIRM="DISABLE_NATIVE_GUEST_NEXT_BOOT",ENABLED="0").stdout)
        self.assertEqual(self.uci("get","wireless.veci_guest.disabled"),"1")
    def test_overlap_stale_and_fw_rollback(self):
        for env,err in (({"ROUTES":"10.0.0.0/8 dev usb0"},"unsupported_or_overlapping_topology"),({"REVISION":"stale"},"stale_configuration"),({"FAIL_FW":"1"},"validation_failed_rollback")):
            r=self.provision(**env)
            self.assertIn(err,r.stdout,r.stderr)
            self.assertEqual({x.name:x.read_bytes() for x in self.cfg.iterdir()},self.original)
