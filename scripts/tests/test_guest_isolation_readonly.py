"""Guest inspector is read-only and reports configuration vs runtime accurately."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime/veci2-guest-check"
ACL=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime/veci2-guest-acl.json"

class GuestIsolationReadonly(unittest.TestCase):
    def test_access_methods_are_read_only(self):
        acl=json.loads(ACL.read_text())["veci-v2-guest-inspect"]
        self.assertEqual(acl["read"]["ubus"],{"veci.v2.guest":["status"]})
        self.assertEqual(acl["write"]["ubus"],{})
        code=SCRIPT.read_text()
        for forbidden in ("uci set ", "uci commit ", "wifi reload", "ifdown", "sysupgrade", "AT+CFUN"):
            self.assertNotIn(forbidden,code)
        self.assertIn('"guest_isolation_verified":null',code)
        self.assertIn('firewall.veci_guest_zone.forward',code)

    def test_configuration_states_using_fake_uci(self):
        with tempfile.TemporaryDirectory() as tmp:
            t=Path(tmp)
            (t/"board").write_text("zbtlink,zbt-we5927\n")
            marker=t/"app-guest"
            marker.write_text("#!/bin/sh\n")
            marker.chmod(0o755)
            code=SCRIPT.read_text().replace("/tmp/sysinfo/board_name",str(t/"board"))
            code=code.replace("/usr/libexec/rpcd/veci.app.guest",str(marker))
            p=t/"guest";p.write_text(code);p.chmod(0o755)
            u=t/"uci"
            u.write_text("""#!/bin/sh
[ "$1" = -q ] && [ "$2" = get ] || exit 1
case "$3" in
 wireless.veci_guest) echo wifi-iface ;;
 network.veci_guest) echo interface ;;
 dhcp.veci_guest) echo dhcp ;;
 firewall.veci_guest_zone) echo zone ;;
 wireless.veci_guest.disabled) echo 1 ;;
 firewall.veci_guest_zone.input) echo REJECT ;;
 firewall.veci_guest_zone.forward) echo REJECT ;;
 wireless.veci_guest.network) echo veci_guest ;;
 firewall.veci_guest_zone.network) echo veci_guest ;;
 *) exit 1 ;;
esac
""")
            u.chmod(0o755)
            env=dict(os.environ,PATH=str(t)+":"+os.environ["PATH"])
            def status():
                p=subprocess.run(["sh",str(t/"guest"),"call","status"],env=env,capture_output=True,text=True,timeout=4)
                self.assertEqual(p.returncode,0,p.stderr)
                return json.loads(p.stdout)
            self.assertEqual(status()["configuration_state"],"configuration_separation_present")
            self.assertIsNone(status()["guest_isolation_verified"])
            u.write_text(u.read_text().replace('echo REJECT ;;','echo ACCEPT ;;',1))
            self.assertEqual(status()["configuration_state"],"configuration_needs_audit")
            (t/"board").write_text("not-our-board\n")
            self.assertEqual(status()["error"],"unsupported_board")

if __name__=="__main__":unittest.main()
