"""Non-live safety checks for General vs Indonesia XL profiles."""
from pathlib import Path
import json, subprocess, unittest
R=Path(__file__).resolve().parents[1]
P=R/"source/veci-indonesia-quota/files/usr/libexec/rpcd/veci.indonesia"
I=R/"source/veci-indonesia-quota/files/usr/sbin/veci-quota-import"
A=R/"source/veci-indonesia-quota/files/usr/share/rpcd/acl.d/veci-indonesia.json"
W=R/".github/workflows/veci-editions.yml"
class TestIndonesia(unittest.TestCase):
    def test_shell_syntax(self):
        for file in [P,I,R/"scripts/prepare-veci.sh"]:
            p=subprocess.run(["sh","-n",str(file)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
    def test_readonly_acl(self):
        a=json.loads(A.read_text())["veci-indonesia-quota"]
        self.assertEqual(a["read"]["ubus"]["veci.indonesia"],["status"])
        self.assertNotIn("write",a)
    def test_provider_local_only(self):
        s=P.read_text()
        self.assertIn('status) quota_status',s)
        for x in ["uclient-fetch","curl ","wget ","AT+","sysupgrade","Authorization:"]:
            self.assertNotIn(x,s)
    def test_cache_writer_restricted(self):
        s=I.read_text()
        for x in ['[ "$(id -u)" = 0 ]',"head -c 2049",'json_load "$payload"','chmod 600 "$temp"','mv -f "$temp" "$CACHE"']:
            self.assertIn(x,s)
    def test_distinct_builds(self):
        s=W.read_text()
        for term in ["edition: [general, indonesia]","veci-we5927-","CONFIG_PACKAGE_veci-indonesia-quota=y","CONFIG_PACKAGE_veci-indonesia-quota is not set","EDITION.txt","j9_offline_audit.py"]:
            self.assertIn(term,s)
    def test_opt_in_pinned_source(self):
        s=(R/"scripts/prepare-veci.sh").read_text()
        self.assertIn("VECI_EDITION:-general",s)
        self.assertIn("veci-indonesia-quota",s)
        self.assertIn('"edition": "$EDITION"',s)
        self.assertEqual(len((R/"source/veci.commit").read_text().strip()),40)
    def test_client_bytes_not_wan(self):
        s=P.read_text()
        for field in ["total_bytes","remaining_bytes","expires_at","updated_at"]:
            self.assertIn(field,s)
if __name__=="__main__":unittest.main()
