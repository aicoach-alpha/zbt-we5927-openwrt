"""Safety contract for router-only rpcd preflight: no calls/restarts or modem."""
from pathlib import Path
import re
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
SH=ROOT/"scripts/veci-sms-rpcd-readonly-preflight-20261013.sh"
PLUGIN=ROOT/"source/veci-sms-inbox-we5927/files/usr/libexec/rpcd/veci.sms"

class ReadOnlyPreflight(unittest.TestCase):
    def test_posix_syntax(self):
        for file in (SH,PLUGIN):
            p=subprocess.run(["sh","-n",str(file)],text=True,capture_output=True)
            self.assertEqual(p.returncode,0,p.stderr)

    def test_list_only_and_never_call_sensitive_methods(self):
        s=SH.read_text()
        self.assertIn('sh "$tmp" list',s)
        self.assertIn("'@.listIndex.scope'",s)
        self.assertIn("'@.listIndex.ack_unread_status'",s)
        self.assertIn('NO_MODEM_COMMANDS_SENT=true',s)
        for forbidden in ('"$tmp" call','veci.sms listIndex','ubus call','CMGL=4',
                          'CUSD=','we5927-at','restart','sysupgrade','uci set'):
            self.assertNotIn(forbidden,s)

    def test_integrity_and_tmp_only(self):
        s=SH.read_text()
        self.assertRegex(s,r"(?m)^PIN=[a-f0-9]{40}$")
        self.assertRegex(s,r"(?m)^RPC_SHA=[a-f0-9]{64}$")
        self.assertIn('mktemp /tmp/veci-rpcd-preflight.',s)
        self.assertIn('trap \'rm -f "$tmp"\' EXIT',s)
        self.assertIn("RPCD_PLUGIN_LIST_CONTRACT_PASS",s)
        self.assertIn("EXISTING_CELLULAR_RPC=",s)
        self.assertIn("V13_FAILED_INSTALL_BACKUP=",s)
        self.assertNotIn("/etc/init.d/rpcd",s)

    def test_rpcd_script_list_contract_in_host_shell(self):
        p=subprocess.run(["sh",str(PLUGIN),"list"],text=True,capture_output=True)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(p.stdout.strip(),'{"listIndex":{"scope":"str","ack_unread_status":"str"}}')

if __name__=="__main__":
    unittest.main()
