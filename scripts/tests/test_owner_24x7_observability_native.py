"""Native shell/procd 24x7 observation acceptance on a disposable device tree.

Never samples the live router. A 72h PHYSICAL UAT is deliberately NOT
claimed by this source-only test suite.
"""
import json,os,subprocess,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime"
SOURCE=RUNTIME/"veci2-observe"
RPC=RUNTIME/"veci2-observe-rpc"
INIT=RUNTIME/"files/etc/init.d/veci2-observe"
ACL=RUNTIME/"veci2-observe-acl.json"


class Native24x7Observability(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix="veci-observe-native-")
        self.addCleanup(self.temporary.cleanup)
        t=Path(self.temporary.name);self.t=t
        self.sys=t/"sys";(self.sys/"usb0/statistics").mkdir(parents=True)
        (self.sys/"wlan0").mkdir(parents=True)
        (self.sys/"usb0/carrier").write_text("1\n")
        (self.sys/"usb0/statistics/rx_errors").write_text("2\n")
        (self.sys/"usb0/statistics/tx_errors").write_text("1\n")
        (self.sys/"wlan0/operstate").write_text("up\n")
        self.uptime=t/"uptime";self.uptime.write_text("999.00 0.00\n")
        self.memory=t/"meminfo";self.memory.write_text("MemAvailable: 30000 kB\n")
        self.board=t/"board";self.board.write_text("zbtlink,zbt-we5927\n")
        self.path=t/"samples"
        self.mode=t/"mode";self.mode.write_text("ready\n")
        self.lock=t/"lock"
        ip=t/"ip"
        ip.write_text("""#!/bin/sh
mode=$(cat "$TEST_MODE")
case "$*" in
  "-o -4 addr show dev usb0")
    [ "$mode" = ready ] && echo '2: usb0 inet 10.23.45.67/24 brd 10.23.45.255' ;;
  "-4 route show default")
    [ "$mode" = ready ] && echo 'default via 10.23.45.1 dev usb0' ;;
esac
""")
        ip.chmod(0o700)
        filt=t/"jsonfilter"
        filt.write_text("""#!/usr/bin/env python3
import sys,json
data=json.load(sys.stdin)
print(data.get("epoch_s",""))
""")
        filt.chmod(0o700)
        source=SOURCE.read_text()
        for orig,replacement in (
            ("/tmp/sysinfo/board_name",str(self.board)),
            ("/sys/class/net/",str(self.sys)+"/"),
            ("/proc/uptime",str(self.uptime)),
            ("/proc/meminfo",str(self.memory)),
            ("/tmp/veci2-observe",str(self.path)),
            ("/var/run/veci2-observe.lock",str(self.lock)),
        ):
            source=source.replace(orig,replacement)
        # BusyBox ash resolves its compiled-in ip applet ahead of PATH in
        # this host fixture. Replace only the two native ip callsites with
        # the disposable fake device tool, preserving real ash execution.
        source=source.replace("ip -o -4",str(ip)+" -o -4")
        source=source.replace("ip -4 route",str(ip)+" -4 route")
        self.provider=t/"observer"
        self.provider.write_text(source);self.provider.chmod(0o700)
        self.env={**os.environ,
            "PATH":str(t)+":"+os.environ.get("PATH",""),
            "TEST_MODE":str(self.mode)}
    def call(self,action):
        p=subprocess.run(["busybox","ash",str(self.provider),action],
            env=self.env,capture_output=True,text=True,timeout=9)
        self.assertEqual(p.returncode,0,p.stderr+"\n"+p.stdout)
        return json.loads(p.stdout)
    def test_native_healthy_degraded_three_samples_unknown_and_no_internet_claim(self):
        self.assertEqual(self.call("status")["telemetry"],"unavailable")
        initial=self.call("once")
        self.assertEqual(initial["state"],"local_path_ready")
        self.assertEqual(initial["usb0_ipv4"],1)
        self.assertEqual(initial["lte_default_route"],1)
        self.assertEqual(initial["alert"],"none")
        self.assertEqual(self.call("status")["sample"]["state"],"local_path_ready")
        self.mode.write_text("down\n")
        (self.sys/"usb0/carrier").write_text("0\n")
        first=self.call("once")
        second=self.call("once")
        third=self.call("once")
        self.assertEqual(first["alert"],"none")
        self.assertEqual(second["alert"],"none")
        self.assertEqual(third["alert"],"degraded_3_samples")
        self.assertEqual(third["state"],"local_path_degraded")
        (self.sys/"usb0/carrier").unlink()
        no_data=self.call("once")
        self.assertEqual(no_data["state"],"unknown")
        self.assertEqual(no_data["alert"],"none")
        self.assertEqual(self.call("status")["sample"]["state"],"unknown")
        self.assertFalse(any(k in json.dumps(third) for k in ("internet_ok","internet_ready","root_cause")))
        self.assertEqual(self.call("status")["hardware_uat"],"not_run")
    def test_privacy_bounded_tmpfs_and_root_only_permissions(self):
        self.call("once")
        data=(self.path/"samples.jsonl")
        self.assertEqual(data.stat().st_mode & 0o777,0o600)
        self.assertEqual(self.path.stat().st_mode & 0o777,0o700)
        body=data.read_text()
        for secret in ("10.23.45.67","00:11:22:33:44:55","imei","ssid","apn"):
            self.assertNotIn(secret.lower(),body.lower())
        self.assertTrue(body.endswith("\n"))
        with data.open("a") as f:
            f.write(('{"state":"local_path_ready"}\n')*24000)
        self.assertGreater(data.stat().st_size,524288)
        self.call("once")
        self.assertLessEqual(len(data.read_text().splitlines()),2880)
        self.assertLess(data.stat().st_size,524288)
    def test_failclosed_other_board_symlink_and_no_router_controls(self):
        self.board.write_text("other-board\n")
        p=subprocess.run(["busybox","ash",str(self.provider),"once"],
            env=self.env,capture_output=True,text=True,timeout=6)
        self.assertNotEqual(p.returncode,0)
        self.assertIn("unsupported_board",p.stdout)
        self.board.write_text("zbtlink,zbt-we5927\n")
        self.path.mkdir()
        (self.path/"samples.jsonl").symlink_to(self.t/"out.txt")
        p=subprocess.run(["busybox","ash",str(self.provider),"once"],
            env=self.env,capture_output=True,text=True,timeout=6)
        self.assertNotEqual(p.returncode,0)
        self.assertFalse((self.t/"out.txt").exists())
        s=SOURCE.read_text()
        actions=s.split("set -eu",1)[1]
        for unsafe in ("AT+CFUN","wifi reload","ifdown","sysupgrade","reboot","/dev/watchdog","gpio_set"):
            self.assertNotIn(unsafe,actions)
    def test_procd_startup_bounded_rpc_acl_and_installed_files(self):
        init=INIT.read_text();self.assertIn("USE_PROCD=1",init)
        self.assertIn("procd_set_param respawn",init)
        self.assertIn("/usr/libexec/veci2-observe daemon",init)
        self.assertIn("START=85",init)
        acl=json.loads(ACL.read_text())["veci-v2-observability"]
        self.assertEqual(acl["read"]["ubus"]["veci.v2.observability"],["status"])
        self.assertEqual(acl["write"]["ubus"],{})
        rpc=RPC.read_text()
        self.assertIn("timeout 3 /usr/libexec/veci2-observe status",rpc)
        pkg=(RUNTIME/"Makefile").read_text()
        for fragment in ("veci2-observe-rpc", "veci2-observe-acl.json",
                         "files/etc/init.d/veci2-observe", "/usr/libexec/veci2-observe",
                         "/etc/init.d/veci2-observe enable"):
            self.assertIn(fragment,pkg)
        web=ROOT/"rebuild/veci-v2/packages/veci-v2-ui"
        html=(web/"files/www/veci2/index.html").read_text()
        js=(web/"files/www/veci2/observability.js").read_text()
        self.assertIn('id="obs-24x7-read"',html)
        self.assertIn('observability.js',html)
        self.assertIn("veci.v2.observability",js)
        self.assertIn("UAT perangkat fisik: belum dilakukan",js)
        self.assertNotIn("innerHTML",js)
        self.assertIn("observability.js",(web/"Makefile").read_text())
        subprocess.run(["node","--check",str(web/"files/www/veci2/observability.js")],
                       capture_output=True,check=True,timeout=5)
        for sh in (SOURCE,RPC,INIT):
            p=subprocess.run(["busybox","ash","-n",str(sh)],capture_output=True,text=True,timeout=5)
            self.assertEqual(p.returncode,0,p.stderr)

if __name__=="__main__":unittest.main()
