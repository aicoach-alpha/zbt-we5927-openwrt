"""Read-only diagnostics, bounded log redaction and LED inventory with real jshn."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
PROVIDER=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime/veci2-system-admin"
UI=ROOT/"rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2"
ACL=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime/veci2-status-acl.json"
PREFIX=Path(os.environ.get("VECI_LIBUBOX_PREFIX") or "/missing-native-libubox")


class ReadonlyNativeDiagnostics(unittest.TestCase):
    def setUp(self):
        if not (PREFIX/"share/libubox/jshn.sh").is_file() or not (PREFIX/"bin/jshn").is_file():
            self.skipTest("real native libubox/jshn host dependency unavailable; CI provisions it")
        self.temp=tempfile.TemporaryDirectory(prefix="veci-system-diag-")
        self.addCleanup(self.temp.cleanup)
        t=Path(self.temp.name)
        self.t=t
        self.board=t/"board";self.board.write_text("zbtlink,zbt-we5927\n")
        self.logs=t/"logread"
        self.logs.write_text("""#!/bin/sh
printf 'service hello\\npassword=SECRET123 token=TOKEN321 IMEI=ABC987\\nnormal=ok\\n'
""")
        self.logs.chmod(0o755)
        self.ip=t/"ip"
        self.ip.write_text("""#!/bin/sh
case "$*" in
 "-4 route show default") echo 'default via 192.168.1.254 dev usb0' ;;
 "-4 addr show dev br-lan") echo ' inet 192.168.1.1/24 brd 192.168.1.255' ;;
esac
""")
        self.ip.chmod(0o755)
        self.carrier=t/"carrier";self.carrier.write_text("1\n")
        self.resolv=t/"resolv.conf";self.resolv.write_text("nameserver 1.1.1.1\n")
        self.leds=t/"leds";(self.leds/"router:green:status").mkdir(parents=True)
        (self.leds/"router:green:status"/"brightness").write_text("1\n")
        code=PROVIDER.read_text()
        code=code.replace("/tmp/sysinfo/board_name",str(self.board))
        code=code.replace("/usr/share/libubox/jshn.sh",str(PREFIX/"share/libubox/jshn.sh"))
        code=code.replace("/sys/class/net/usb0/carrier",str(self.carrier))
        code=code.replace("/tmp/resolv.conf.d/resolv.conf.auto",str(self.resolv))
        code=code.replace("/sys/class/leds/",str(self.leds)+"/")
        self.provider=t/"provider";self.provider.write_text(code)
        self.env={**os.environ,
            "PATH":str(t)+":"+str(PREFIX/"bin")+":"+os.environ.get("PATH",""),
            "LD_LIBRARY_PATH":str(PREFIX/"lib")+":"+os.environ.get("LD_LIBRARY_PATH",""),
        }

    def call(self,method):
        proc=subprocess.run(["bash",str(self.provider),"call",method],
                            env=self.env,text=True,capture_output=True,timeout=9)
        self.assertEqual(proc.returncode,0,proc.stderr+"\n"+proc.stdout)
        return json.loads(proc.stdout)

    def test_redacts_sensitive_logs_and_keeps_bounded_readonly(self):
        out=self.call("logs")
        self.assertTrue(out["ok"],out)
        self.assertIn("service hello",out["logs"])
        for secret in ("SECRET123","TOKEN321","ABC987"):
            self.assertNotIn(secret,out["logs"])
        self.assertIn("[REDACTED]",out["logs"])
        self.assertIn("normal=ok",out["logs"])
        source=PROVIDER.read_text()
        self.assertIn("logread -l 50",source)
        self.assertNotIn("logread -f",source)

    def test_diagnostics_provides_local_route_dns_lan_and_carrier(self):
        out=self.call("diagnostics")
        self.assertTrue(out["ok"],out)
        self.assertEqual(out["state"],"observation_only")
        self.assertEqual(out["lan_ipv4"],"192.168.1.1/24")
        self.assertEqual(out["first_dns"],"1.1.1.1")
        self.assertEqual(out["lte_carrier"],"1")
        self.assertIn("dev usb0",out["default_route"])
        self.carrier.write_text("bad\n")
        out=self.call("diagnostics")
        self.assertEqual(out["lte_carrier"],"unknown")
        self.resolv.unlink()
        out=self.call("diagnostics")
        self.assertEqual(out["first_dns"],"unavailable")

    def test_led_inventory_and_unauthorized_board_fail_closed(self):
        out=self.call("leds")
        self.assertTrue(out["ok"],out)
        self.assertTrue(any(x["name"]=="router:green:status" and x["brightness"]=="1" for x in out["leds"]))
        self.board.write_text("unknown-board\n")
        self.assertEqual(self.call("diagnostics")["error"],"unsupported_board")

    def test_authenticated_rpc_coverage_and_no_mutating_operations(self):
        acl=json.loads(ACL.read_text())["veci-v2-system"]
        self.assertIn("diagnostics",acl["read"]["ubus"]["veci.v2.system"])
        self.assertEqual(acl["write"]["ubus"]["veci.v2.system"],["setNtp"])
        js=(UI/"owner-controls.js").read_text()
        self.assertIn("call('veci.v2.system','diagnostics')",js)
        self.assertIn("observasi",js)
        source=PROVIDER.read_text()
        for forbidden in ("ifdown","ifup","AT+CFUN","wifi reload","sysupgrade"):
            self.assertNotIn(forbidden,source)
        subprocess.run(["busybox","ash","-n",str(PROVIDER)],check=True,capture_output=True,timeout=5)
        subprocess.run(["node","--check",str(UI/"owner-controls.js")],check=True,capture_output=True,timeout=5)


if __name__=="__main__":unittest.main()
