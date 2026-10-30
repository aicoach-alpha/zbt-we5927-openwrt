# Guest removal must never ACK success unless all cleanup operations succeed.
import json, pathlib, re, subprocess, tempfile, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'source/veci-app-guest/files/usr/libexec/rpcd/veci.app.guest'
PKG=ROOT/'source/veci-app-guest/Makefile'

def cleanup_source():
    data=SCRIPT.read_text()
    match=re.search(r'(?ms)^method_cleanup\(\) \{\n.*?^\}',data)
    if not match:raise AssertionError('cleanup function missing')
    return match.group()

def run_case(disable=0,commit_fail='',restore=0,delete_fail=''):
    with tempfile.TemporaryDirectory() as directory:
        root=pathlib.Path(directory)
        marker=root/'actions'
        code=cleanup_source()
        stub='''
portal_snapshot_begin() { echo snapshot >> "$AUDIT"; return 0; }
portal_snapshot_discard() { echo discard >> "$AUDIT"; }
portal_snapshot_restore() { echo restore >> "$AUDIT"; return RESTORE_RC; }
disable_portal() { echo disable >> "$AUDIT"; return DISABLE_RC; }
service_restart() { echo "restart:$1" >> "$AUDIT"; return 0; }
wifi() { echo reload >> "$AUDIT"; return 0; }
uci() {
  echo "uci:$*" >> "$AUDIT";
  if [ "$1" = commit ] && [ "$2" = BAD_COMMIT ]; then return 1; fi
  if [ "$1" = -q ] && [ "$2" = delete ] && [ "$3" = BAD_DELETE ]; then return 1; fi
  return 0;
}
'''.replace('DISABLE_RC',str(disable)).replace('RESTORE_RC',str(restore)).replace('BAD_COMMIT',commit_fail).replace('BAD_DELETE',delete_fail)
        content='AUDIT='+str(marker)+'\n'+stub+'\n'+code+'\nmethod_cleanup\n'
        p=subprocess.run(['sh','-c',content],capture_output=True,text=True,timeout=8)
        return p,json.loads(p.stdout),marker.read_text().splitlines()

class GuestCleanupSafetyTests(unittest.TestCase):
    def test_cleanup_disable_failure_does_not_modify_rest(self):
        p,data,actions=run_case(disable=1)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertFalse(data['ok'])
        self.assertEqual(data['error'],'guest_cleanup_disable_failed_rolled_back')
        self.assertEqual(actions,['snapshot','disable','restore'])
    def test_cleanup_failed_commit_returns_false_and_restores(self):
        p,data,actions=run_case(commit_fail='wireless')
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertFalse(data['ok'])
        self.assertEqual(data['error'],'guest_cleanup_failed_rolled_back')
        self.assertIn('uci:commit wireless',actions)
        self.assertIn('restore',actions)
        self.assertNotIn('discard',actions)
    def test_existing_config_delete_failure_is_rolled_back(self):
        p,data,actions=run_case(delete_fail='firewall.veci_guest_dns')
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertFalse(data['ok'])
        self.assertEqual(data['error'],'guest_cleanup_failed_rolled_back')
        self.assertIn('uci:-q delete firewall.veci_guest_dns',actions)
        self.assertIn('restore',actions)
    def test_cleanup_failed_rollback_is_explicit(self):
        p,data,actions=run_case(disable=1,restore=1)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertFalse(data['ok'])
        self.assertEqual(data['error'],'guest_cleanup_rollback_incomplete')
    def test_cleanup_success_only_after_commits_and_services(self):
        p,data,actions=run_case()
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertTrue(data['ok'])
        self.assertIn('uci:commit network',actions)
        self.assertIn('uci:commit firewall',actions)
        self.assertIn('restart:uspot',actions)
        self.assertIn('reload',actions)
        self.assertEqual(actions[-1],'discard')
    def test_package_is_uprev_and_shell_parses(self):
        self.assertIn('PKG_RELEASE:=4',PKG.read_text())
        p=subprocess.run(['sh','-n',str(SCRIPT)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
if __name__=='__main__':unittest.main()
