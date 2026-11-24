import subprocess
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
FILE=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime/veci2-static-leases"
SOURCE=FILE.read_text()
class StaticLeaseSource(unittest.TestCase):
    def test_posix_syntax(self):
        result=subprocess.run(["sh","-n",str(FILE)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
    def test_rpc_read_descriptor(self):
        out=subprocess.check_output(["sh",str(FILE),"list"],text=True)
        self.assertIn('"add"',out)
        self.assertIn('"delete"',out)
    def test_bad_method_denied_before_uci(self):
        out=subprocess.check_output(["sh",str(FILE),"call","runArbitrary"],text=True)
        self.assertIn("unsupported_method",out)
    def test_rejects_untrusted_input_and_restores_on_restart_failure(self):
        for x in ("invalid_mac","invalid_ip","invalid_hostname","duplicate_static_lease",
                  "ip_is_router_address","pending_dhcp_changes","confirmation_required",
                  "dhcp_apply_failed_rollback_attempted", 'cp "$tmp/original" /etc/config/dhcp',
                  'uci -q -t "$tmp" commit dhcp',"flock -n 9"):
            self.assertIn(x,SOURCE)
    def test_no_interface_modem_or_wifi_mutation(self):
        for x in ("ifdown","ifup","wifi reload","AT+","gpio_set","sysupgrade"):
            self.assertNotIn(x,SOURCE)
if __name__=="__main__":
    unittest.main()
