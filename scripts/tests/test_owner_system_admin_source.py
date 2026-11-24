from pathlib import Path
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[2]
FILE=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime/veci2-system-admin"
SOURCE=FILE.read_text()

class SystemSource(unittest.TestCase):
    def test_shell(self):
        p=subprocess.run(["sh","-n",str(FILE)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
    def test_read_methods(self):
        p=subprocess.run(["sh",str(FILE),"list"],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        for field in ('"ntp"','"setNtp"','"logs"','"leds"','"observability"'):
            self.assertIn(field,p.stdout)
    def test_reject_unsupported(self):
        p=subprocess.run(["sh",str(FILE),"call","reboot"],capture_output=True,text=True)
        self.assertIn("unsupported_method",p.stdout)
    def test_guarded_ntp_change_rollback(self):
        for phrase in ("SET_NTP","invalid_first_ntp","invalid_second_ntp",
                       "pending_system_changes","flock -n 9",
                       "/etc/init.d/sysntpd restart",
                       'cp "$tmp/original" /etc/config/system'):
            self.assertIn(phrase,SOURCE)
    def test_no_modem_or_wifi_mutations(self):
        for phrase in ("ifup lte","wifi reload","sysupgrade","gpio_set","AT+CFUN"):
            self.assertNotIn(phrase,SOURCE)
if __name__=="__main__":
    unittest.main()
