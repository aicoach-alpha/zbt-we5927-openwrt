"""MT76 station evidence guard: read-only, privacy-preserving, no false PASS."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/"scripts/router/veci-mt76-client-evidence-readonly.sh"

class Mt76StationEvidence(unittest.TestCase):
 def run_case(self,active=False,mismatch=False,board="zbtlink,zbt-we5927"):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)
   (root/"board").write_text(board+"\n")
   (root/"libubox").mkdir()
   # Simulated json keys: tests count logic, not libubox internals.
   (root/"libubox/jshn.sh").write_text("""json_load() {
  case "$1" in
    *'authorized'*) mock_clients='02:aa:bb:cc:dd:ee' ;;
    *'clients'*) mock_clients='' ;;
    *) return 1 ;;
  esac
}
json_select() { [ "$1" = clients ]; }
json_get_keys() { keys="$mock_clients"; }
""")
   b=root/"bin";b.mkdir()
   def create(name,body):
    p=b/name;p.write_text("#!/bin/sh\n"+body+"\n");p.chmod(0o755)
   create("ubus", """case "$*" in
  *'network.wireless status'*)
    printf '%s\\n' '{"radio0":{"up":true,"interfaces":[{"section":"default_radio0","ifname":"phy0-ap0"}]}}' ;;
  *'hostapd.phy0-ap0 get_clients'*)
    if [ "$ACTIVE" = 1 ] && [ "$MISMATCH" != 1 ]; then
      printf '%s\\n' '{"clients":{"02:aa:bb:cc:dd:ee":{"authorized":true}}}'
    else
      printf '%s\\n' '{"clients":{}}'
    fi ;;
  *) exit 1 ;;
esac""")
   create("jsonfilter", """case "$*" in
  *ifname*) echo phy0-ap0 ;;
  *radio0.up*) echo true ;;
  *) exit 1 ;;
esac""")
   create("iw", """case "$*" in
  'dev phy0-ap0 info') printf 'Interface phy0-ap0\\n type AP\\n' ;;
  'dev phy0-ap0 station dump')
    if [ "$ACTIVE" = 1 ]; then
      echo 'Station 02:aa:bb:cc:dd:ee (on phy0-ap0)'
    fi ;;
  *) exit 1 ;;
esac""")
   create("sleep","exit 0")
   script=root/"read-only.sh"
   v=SOURCE.read_text().replace("/tmp/sysinfo/board_name",str(root/"board"))
   v=v.replace("/usr/share/libubox/jshn.sh",str(root/"libubox/jshn.sh"))
   # The real script deliberately spaces samples 2 seconds apart; substitute
   # only the test copy's sleep because BusyBox ash can use its built-in applet.
   v=v.replace('then sleep 2; fi','then :; fi')
   script.write_text(v)
   env={**os.environ,"ACTIVE":"1" if active else "0",
     "MISMATCH":"1" if mismatch else "0",
     "PATH":str(b)+":"+os.environ.get("PATH","")}
   out=subprocess.run(["busybox","ash",str(script)],env=env,
                      capture_output=True,text=True,timeout=8)
   return out
 def test_zero_stations_is_not_passed_as_load_test(self):
  r=self.run_case()
  self.assertEqual(r.returncode,0,r.stderr)
  self.assertEqual(r.stdout.count("MATCH=MATCH"),5)
  self.assertIn("POSITIVE_CLIENT_SAMPLES=0/5",r.stdout)
  self.assertIn("RESULT=NO_ASSOCIATED_CLIENT_OBSERVED",r.stdout)
  self.assertIn("MT76_DRIVER_ROOT_CAUSE_RESOLVED=NOT_PROVEN",r.stdout)
 def test_one_active_station_detected_without_mac_output(self):
  r=self.run_case(active=True)
  self.assertEqual(r.returncode,0,r.stderr)
  self.assertIn("POSITIVE_CLIENT_SAMPLES=5/5",r.stdout)
  self.assertIn("RESULT=CLIENT_ASSOCIATION_OBSERVED_NOT_STRESS_PASS",r.stdout)
  self.assertNotIn("02:aa:bb:cc:dd:ee",r.stdout)
 def test_disagreement_is_never_passed(self):
  r=self.run_case(active=True,mismatch=True)
  self.assertEqual(r.returncode,0,r.stderr)
  self.assertIn("MATCH=MISMATCH",r.stdout)
  self.assertIn("RESULT=INCONCLUSIVE_COUNTER_FAILURE_OR_MISMATCH",r.stdout)
 def test_non_we5927_board_aborts(self):
  r=self.run_case(board="not-a-we5927")
  self.assertEqual(r.returncode,3)
  self.assertIn("RESULT=ABORT",r.stdout)
 def test_script_never_performs_risky_mutations(self):
  s=SOURCE.read_text()
  code="\n".join(line for line in s.splitlines()
                  if not line.lstrip().startswith("#"))
  for word in ("uci set","uci commit","network reload","wifi reload",
               "wifi down","wifi up","ifdown","ifup","mtd write",
               "sysupgrade","reboot","AT+CFUN","iw dev \"$iface\" scan"):
   self.assertNotIn(word,code)
  subprocess.run(["busybox","ash","-n",str(SOURCE)],check=True,timeout=4)

if __name__=="__main__":unittest.main()
