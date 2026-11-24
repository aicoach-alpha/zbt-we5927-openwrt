"""Single procd owner vs accidental second netifd — strict read-only telemetry."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BACKEND=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime/veci2-status"
ACL=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime/veci2-status-acl.json"

class NetworkHealthTruth(unittest.TestCase):
    def test_runtime_acl_and_only_read_operations(self):
        s=BACKEND.read_text()
        subprocess.run(["sh","-n",str(BACKEND)],check=True)
        acl=json.loads(ACL.read_text())
        self.assertIn("networkHealth",acl["veci-v2-runtime"]["read"]["ubus"]["veci.v2"])
        self.assertEqual(acl["veci-v2-runtime"]["write"]["ubus"],{})
        self.assertIn("call:networkHealth)",s)
        self.assertIn('source":"live_procfs_procd_kernel',s)
        chunk=s.split("    call:networkHealth)",1)[1].split("    call:traffic)",1)[0]
        for bad in ("kill ", "pkill", "killall", "reboot", "network reload",
                    "network restart", "ifup ", "ifdown ", "uci set", "uci commit",
                    "AT+CFUN", "usb_modeswitch"):
            self.assertNotIn(bad,chunk)
        for secret in ("imei", "iccid", "password", "msisdn", "imsi"):
            self.assertNotIn(secret,chunk.lower())

    def run_network(self, includes_orphan: bool, has_owner: bool):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for suffix in ("1366","16862"):
                (root/suffix).mkdir()
                (root/suffix/"status").write_text("Name:\tnetifd\nState:\tS (sleeping)\nPPid:\t1\n")
                (root/suffix/"exe").symlink_to("/sbin/netifd")
            (root/"meminfo").write_text("MemAvailable: 16000 kB\n")
            (root/"uptime").write_text("1234.3 100.0\n")
            (root/"loadavg").write_text("0.25 0.10 0.00 1/55 9999\n")
            netdev=root/"netdev"/"usb0";netdev.mkdir(parents=True)
            source=BACKEND.read_text()
            source=source.rsplit('main "$@"',1)[0]
            source=source.replace('/proc/',str(root)+'/')
            source=source.replace('/sys/class/net/',str(root/'netdev')+'/')
            stubs="""
pidof() {
  case "$1" in
    netifd) echo "$test_pids";;
    udhcpc) echo '999 888';;
  esac
}
ubus() {
  if [ "$has_owner" = 1 ]; then echo '{"network":{"instances":[{"pid":1366}]}}'; fi
}
jsonfilter() {
  if [ "$has_owner" = 1 ]; then echo 1366; fi
}
ip() {
  case "$*" in
     *"addr show dev usb0"*) echo "11: usb0 inet 192.168.7.120/24";;
     *"route show default dev usb0"*) echo "default via 192.168.7.1 dev usb0";;
  esac
}
main call networkHealth
"""
            state="1366 16862" if includes_orphan else "1366"
            cmd=source+"\n"+"test_pids='"+state+"'\n"+"has_owner="+("1" if has_owner else "0")+"\n"+stubs
            p=subprocess.run(["sh","-c",cmd],capture_output=True,text=True,timeout=5)
            self.assertEqual(p.returncode,0,p.stderr)
            return json.loads(p.stdout.strip())

    def test_duplicate_reports_excess_only_with_procd_identity(self):
        x=self.run_network(True,True)
        self.assertEqual(x["netifd_count"],2)
        self.assertTrue(x["procd_netifd_owner_confirmed"])
        self.assertEqual(x["procd_netifd_pid"],1366)
        self.assertEqual(x["procd_netifd_state"],"S")
        self.assertEqual(x["unmanaged_netifd_count"],1)
        self.assertEqual(x["udhcpc_process_count"],2)
        self.assertEqual(x["uptime_seconds"],1234)
        self.assertEqual(x["memory_available_kb"],16000)
        self.assertTrue(x["lte_ipv4"])
        self.assertTrue(x["lte_default_route"])

    def test_single_owner_is_healthy(self):
        x=self.run_network(False,True)
        self.assertEqual(x["netifd_count"],1)
        self.assertEqual(x["unmanaged_netifd_count"],0)
        self.assertTrue(x["procd_netifd_owner_confirmed"])

    def test_unknown_procd_owner_never_invents_extra_count(self):
        x=self.run_network(True,False)
        self.assertEqual(x["netifd_count"],2)
        self.assertFalse(x["procd_netifd_owner_confirmed"])
        self.assertIsNone(x["unmanaged_netifd_count"])
        self.assertIsNone(x["procd_netifd_pid"])
        self.assertIsNone(x["procd_netifd_state"])

if __name__=="__main__":
    unittest.main()
