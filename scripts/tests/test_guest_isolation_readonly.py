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
            self.assertIn(status()["guest_ap_runtime"], ("not_observed","unavailable"))
            # Simulate netifd and hostapd in PATH. The radio can be up while
            # the UCI startup configuration says disabled (e.g. staged edit).
            for name,body in {
                "ubus": """#!/bin/sh
case "$*" in
  *network.wireless*) echo '{"radio0":{}}' ;;
  *get_status*) echo '{"status":"ENABLED"}' ;;
  *) exit 1 ;;
esac
""",
                "jsonfilter": """#!/bin/sh
case "$2" in
  *ifname*) echo phy0-ap1 ;;
  *@.status*) echo "$MOCK_AP_STATUS" ;;
  *) exit 1 ;;
esac
""",
                "iw": """#!/bin/sh
[ "$*" = "dev phy0-ap1 info" ] || exit 1
echo 'Interface phy0-ap1'
echo ' type AP'
"""
            }.items():
                f=t/name
                f.write_text(body)
                f.chmod(0o755)
            env['MOCK_AP_STATUS']='ENABLED'
            live=status()
            self.assertFalse(live["enabled_configured"],live)
            self.assertEqual(live["guest_ap_runtime"],"ap_running_unverified",live)
            self.assertIsNone(live["guest_isolation_verified"])
            # Saved UCI enabled without on-air hostapd is NOT a live AP pass.
            u.write_text(u.read_text().replace('wireless.veci_guest.disabled) echo 1','wireless.veci_guest.disabled) echo 0'))
            env['MOCK_AP_STATUS']='DISABLED'
            staged=status()
            self.assertTrue(staged["enabled_configured"],staged)
            self.assertEqual(staged["guest_ap_runtime"],"not_observed",staged)
            env['MOCK_AP_STATUS']='ENABLED'
            self.assertEqual(status()["guest_ap_runtime"],"ap_running_unverified")
            u.write_text(u.read_text().replace('echo REJECT ;;','echo ACCEPT ;;',1))
            self.assertEqual(status()["configuration_state"],"configuration_needs_audit")
            (t/"board").write_text("not-our-board\n")
            self.assertEqual(status()["error"],"unsupported_board")

    def test_guest_gui_does_not_claim_staged_ap_is_live(self):
        ui=ROOT/"rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2/guest-check.js"
        script=ui.read_text()
        for marker in ("guest_ap_runtime","Konfigurasi startup guest",
                       "AP belum teramati aktif","Isolasi klien: belum diuji"):
            self.assertIn(marker,script)
        subprocess.run(["node","--check",str(ui)],check=True,timeout=5)

if __name__=="__main__":unittest.main()
