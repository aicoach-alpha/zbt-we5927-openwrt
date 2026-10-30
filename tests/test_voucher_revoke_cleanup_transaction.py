# Offline proof that voucher revoke and uninstall cleanup cannot silently fail.
import json, pathlib, subprocess, tempfile, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
SRC=ROOT/'source/veci-app-voucher/files/usr/libexec/rpcd/veci.app.voucher'
PKG=ROOT/'source/veci-app-voucher/Makefile'
NAMES=['safe_code','section_for_code','voucher_tx_begin','voucher_tx_end',
       'voucher_tx_rollback','voucher_tx_failed','method_revoke','method_cleanup_all',
       'cleanup_expired','method_cleanup']

def function(source,name):
    anchor=name+'() {'
    return anchor+source.split(anchor,1)[1].split('\n}',1)[0]+'\n}'

def invoke(action='revoke',fail_commit='',restart_failure=False,lock_busy=False,future_expiry=False):
    with tempfile.TemporaryDirectory(prefix='veci-voucher-tx-test-') as tmp:
        root=pathlib.Path(tmp)
        cfg=root/'config';cfg.mkdir()
        originals={'uspot':'USPOT:ORIGINAL\n','veci_voucher':'VOUCHERS:ORIGINAL\n'}
        for name,val in originals.items():
            (cfg/name).write_text(val)
        lock=root/'tx.lock'
        if lock_busy:lock.mkdir()
        text=SRC.read_text()
        sections='\n'.join(function(text,name) for name in NAMES)
        sections=sections.replace('/etc/config/',str(cfg)+'/')
        sections=sections.replace('/tmp/veci-voucher-batch.lock',str(lock))
        sections=sections.replace('/tmp/veci-voucher-tx.XXXXXX',str(root/'snapshot.XXXXXX'))
        sections=sections.replace('/etc/init.d/uspot restart','uspot_restart')
        script='''
AUDIT='AUDIT_PATH'
FAIL_COMMIT='FAIL_VALUE'
RESTART_FAILURE=RESTART_VALUE
jsonfilter() { echo REVOKE123; }
disconnect_voucher_clients() { echo disconnect >> "$AUDIT"; }
uspot_restart() {
 echo restart >> "$AUDIT"
 if [ "$RESTART_FAILURE" = 1 ]; then return 1; fi
 return 0
}
uci() {
 echo "uci:$*" >> "$AUDIT"
 case "$*" in
   "show veci_voucher") printf 'veci_voucher.v_revoke123=voucher\\n'; return 0;;
   "-q get veci_voucher.v_revoke123.expires") echo EXPIRY_VALUE; return 0;;
   "-q get veci_voucher.v_revoke123.code") echo REVOKE123; return 0;;
   *"get veci_voucher.v_revoke123"|*"get uspot.veci_voucher_v_revoke123"|*"get uspot.veci_guest") return 0;;
   "-q delete veci_voucher.v_revoke123") echo MUTATED > 'CFG_VOUCHER'; return 0;;
   "-q delete uspot.veci_voucher_v_revoke123") echo MUTATED > 'CFG_USPOT'; return 0;;
   "commit "*)
      if [ "$2" = "$FAIL_COMMIT" ]; then return 1; fi
      return 0;;
 esac
 return 0
}
'''
        script=script.replace('AUDIT_PATH',str(root/'audit'))
        script=script.replace('FAIL_VALUE',fail_commit)
        script=script.replace('RESTART_VALUE','1' if restart_failure else '0')
        script=script.replace('CFG_VOUCHER',str(cfg/'veci_voucher'))
        script=script.replace('CFG_USPOT',str(cfg/'uspot'))
        script=script.replace('EXPIRY_VALUE','99999999999' if future_expiry else '1')
        script+='\n'+sections+'\n'
        if action=='revoke':
            script+='printf \'{"code":"REVOKE123"}\n\' | method_revoke\n'
        elif action=='expire':
            script+='method_cleanup\n'
        else:
            script+='method_cleanup_all\n'
        result=subprocess.run(['sh','-c',script],capture_output=True,text=True,timeout=8)
        audit=(root/'audit').read_text().splitlines() if (root/'audit').exists() else []
        content={k:(cfg/k).read_text() for k in originals}
        if not result.stdout.strip(): raise AssertionError('shell failed rc='+str(result.returncode)+' stderr='+repr(result.stderr)+' script_tail='+repr(script[-420:]))
        return result,json.loads(result.stdout),audit,content,{k:v.replace('\n','\n') for k,v in originals.items()},lock.exists()

class VoucherLifecycleTests(unittest.TestCase):
    def test_revoke_failure_restores_original_credentials(self):
        proc,data,audit,content,expected,locked=invoke('revoke',fail_commit='uspot')
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertFalse(data['ok'])
        self.assertEqual(data['error'],'voucher_revoke_failed_rolled_back')
        self.assertEqual(content,expected)
        self.assertFalse(locked)
        self.assertNotIn('disconnect',audit)
    def test_cleanup_failure_restores_original_credentials(self):
        proc,data,audit,content,expected,locked=invoke('cleanup',fail_commit='uspot')
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertFalse(data['ok'])
        self.assertEqual(data['error'],'voucher_cleanup_failed_rolled_back')
        self.assertEqual(content,expected)
        self.assertFalse(locked)
    def test_revoke_success_only_after_restart(self):
        proc,data,audit,content,expected,locked=invoke('revoke')
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertTrue(data['ok'])
        self.assertIn('uci:commit veci_voucher',audit)
        self.assertIn('uci:commit uspot',audit)
        self.assertLess(audit.index('restart'),audit.index('disconnect'))
        self.assertFalse(locked)
    def test_cleanup_success_only_after_restart(self):
        proc,data,audit,content,expected,locked=invoke('cleanup')
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertTrue(data['ok'])
        self.assertIn('uci:commit uspot',audit)
        self.assertIn('restart',audit)
        self.assertFalse(locked)
    def test_service_restart_failure_is_never_success(self):
        proc,data,audit,content,expected,locked=invoke('revoke',restart_failure=True)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertFalse(data['ok'])
        self.assertEqual(data['error'],'voucher_revoke_rollback_incomplete')
        self.assertFalse(locked)
    def test_mutual_exclusion_with_batch(self):
        proc,data,audit,content,expected,locked=invoke('cleanup',lock_busy=True)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertFalse(data['ok'])
        self.assertEqual(data['error'],'voucher_cleanup_snapshot_or_lock_failed')
        self.assertEqual(content,expected)
        self.assertTrue(locked)
    def test_expired_cleanup_failure_restores_credentials(self):
        p,data,audit,content,expected,locked=invoke('expire',fail_commit='uspot')
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertFalse(data['ok'])
        self.assertEqual(data['error'],'voucher_expiry_cleanup_failed')
        self.assertEqual(content,expected)
        self.assertNotIn('disconnect',audit)
        self.assertFalse(locked)
    def test_expired_cleanup_success_disconnects_after_restart(self):
        p,data,audit,content,expected,locked=invoke('expire')
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertTrue(data['ok'])
        self.assertLess(audit.index('restart'),audit.index('disconnect'))
        self.assertFalse(locked)
    def test_expiry_not_yet_due_is_a_noop(self):
        p,data,audit,content,expected,locked=invoke('expire',future_expiry=True)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertTrue(data['ok'])
        self.assertEqual(content,expected)
        self.assertFalse(any(item.startswith('uci:commit') for item in audit))
        self.assertNotIn('disconnect',audit)
        self.assertFalse(locked)
    def test_package_revision_and_syntax(self):
        self.assertIn('PKG_RELEASE:=3',PKG.read_text())
        r=subprocess.run(['sh','-n',str(SRC)],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
if __name__=='__main__':unittest.main()
