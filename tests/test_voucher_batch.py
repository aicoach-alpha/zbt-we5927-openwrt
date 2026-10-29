import pathlib
import re
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / 'source/veci-app-voucher/files/usr/libexec/rpcd/veci.app.voucher'

class VoucherBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.script = SRC.read_text()
    def test_shell_parses(self):
        res = subprocess.run(['sh','-n',str(SRC)],capture_output=True,text=True)
        self.assertEqual(res.returncode,0,res.stderr)
    def test_batch_limit_and_runtime_validation(self):
        fn = re.search(r'(?ms)^safe_batch_count\(\) \{.*?^\}',self.script).group()
        for count,expected in [('1',0),('20',0),('0',1),('21',1),('-1',1),('abc',1),('999999999',1)]:
            res=subprocess.run(['sh','-c',fn+'\nsafe_batch_count "$1"','sh',count])
            self.assertEqual(res.returncode,expected,count)
    def test_transaction_fail_closed(self):
        src=self.script
        batch=src.split('method_create_batch() {',1)[1].split('\nmethod_revoke() {',1)[0]
        self.assertIn('json_add_boolean batch_supported 1', src)
        for keyword in ['voucher_batch_busy','voucher_capacity_limit','secure_random_unavailable',
          'voucher_batch_failed_rolled_back','voucher_batch_rollback_incomplete','/dev/urandom',
          'batch_rollback()', 'batch_cleanup()', 'json_add_array vouchers',
          'uci -q batch < "$dir/commands"', 'uci commit veci_voucher',
          '/etc/init.d/uspot restart', 'createBatch) method_create_batch']:
            self.assertIn(keyword,src,keyword)
        self.assertLess(batch.index('uci -q batch < "$dir/commands"'),batch.index('json_add_array vouchers'))
        self.assertLess(src.index('cp -p "/etc/config/$name" "$dir/$name"'),src.index('uci -q batch < "$dir/commands"'))
    def test_single_create_fail_closed_and_shared_lock(self):
        create=self.script.split('method_create() {',1)[1].split('\n}',1)[0]
        for item in ('voucher_backup_failed','voucher_create_failed_rolled_back',
          'voucher_create_rollback_incomplete','/tmp/veci-voucher-batch.lock',
          'uci commit veci_voucher','uci commit uspot','/etc/init.d/uspot restart'):
            self.assertIn(item,create)
        self.assertLess(create.index('cp -p "/etc/config/$name" "$work/$name"'),
                        create.index('uci -q batch <<EOF'))
    def test_manifest_release_bumped(self):
        self.assertIn('PKG_RELEASE:=2', (ROOT/'source/veci-app-voucher/Makefile').read_text())

if __name__=='__main__': unittest.main()
