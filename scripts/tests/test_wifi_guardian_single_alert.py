"""The MT7603 guardian must not evict first-failure evidence with alert floods."""
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]
GUARDIAN=ROOT/"source/veci-wifi-guardian/veci-wifi-guardian"
PROVIDER=ROOT/"source/veci-cellular-we5927/files/usr/libexec/rpcd/veci.cellular"
HOME=ROOT/"source/veci-core/veci/js/pages/home.js"
SOURCE=GUARDIAN.read_text()
SH=shutil.which("sh") or "/bin/sh"


def daemon_body():
    match=re.search(r"(?ms)^daemon\(\) \{\n.*?^\}\n",SOURCE)
    if not match:
        raise AssertionError("daemon() missing")
    return match.group(0)


def simulate(recover_at, iterations):
    setup="""
TAG=veci-wifi-guardian
CFG=veci_performance.wifi
reset_count=0
iterations=0
cfg() { :; }
number() { echo "$2"; }
radio_wanted() { return 0; }
radio_running() {
  iterations=$((iterations+1))
  [ "$iterations" -eq RECOVERY_POINT ] && return 0
  return 1
}
rx_pse_resets() { echo unknown; }
logger() { echo "ALERT:$*"; }
write_state() { echo "STATE:$phase"; }
sleep() {
  reset_count=$((reset_count+1))
  [ "$reset_count" -ge TOTAL_ITERATIONS ] && exit 0
}
"""
    setup=setup.replace("RECOVERY_POINT",str(recover_at))
    setup=setup.replace("TOTAL_ITERATIONS",str(iterations))
    cp=subprocess.run([SH,"-c",setup+"\n"+daemon_body()+"\ndaemon\n"],
                      text=True,capture_output=True,timeout=5)
    if cp.returncode:
        raise AssertionError(cp.stderr)
    return cp.stdout.splitlines()


class GuardianLogDebounce(unittest.TestCase):
    def test_sustained_missing_bss_logs_once_not_every_90_seconds(self):
        rows=simulate(recover_at=100,iterations=10)
        alerts=[r for r in rows if "AP runtime unavailable" in r]
        self.assertEqual(len(alerts),1)
        self.assertEqual(len(rows),12)
        self.assertEqual(rows[-1],"STATE:manual_recovery_required")

    def test_recovery_rearms_new_outage_alert(self):
        rows=simulate(recover_at=4,iterations=10)
        alerts=[r for r in rows if "AP runtime unavailable" in r]
        self.assertEqual(len(alerts),2)
        self.assertIn("STATE:ready",rows)
        self.assertEqual(rows[-1],"STATE:manual_recovery_required")

    def test_disabled_and_running_rearm_flags_and_no_radio_reload(self):
        daemon=daemon_body()
        self.assertIn('alerted=0',daemon)
        self.assertIn('if [ "$alerted" -eq 0 ]',daemon)
        self.assertNotRegex(daemon,r"\b(?:wifi|ifup|ifdown|reboot|power_cycle|usb_repair)\s")
        self.assertIn('auto_recover=0',SOURCE)

    def test_status_is_visible_in_cellular_provider_and_home(self):
        provider=PROVIDER.read_text()
        home=HOME.read_text()
        self.assertIn("manual_recovery_required|driver_reset_observed|radio_recovery",provider)
        self.assertIn("manual_recovery_required: 'Access point missing",home)
        self.assertIn("driver_reset_observed: 'Wi-Fi driver reset",home)


if __name__=="__main__":
    unittest.main()
