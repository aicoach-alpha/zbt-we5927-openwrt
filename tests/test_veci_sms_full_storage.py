import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / 'source/veci-cellular-we5927/files/usr/libexec'
PDU = '00' * 12

class FullSmsStorageTest(unittest.TestCase):
    def fixture(self, name, store_name, root):
        # A transformed isolated copy, NEVER modifying /etc or the real router.
        original = (FILES / ('veci-sms-'+name)).read_text()
        store = root / store_name
        store.touch(mode=0o600)
        flag = root / 'veci_sms'
        flag.touch(mode=0o600)
        original = original.replace('/etc/veci-sms-'+store_name, str(store))
        original = original.replace('/etc/config/veci_sms', str(flag))
        original = original.replace('$(id -u)', '$(printf 0)')
        original = original.replace('$(cat /tmp/sysinfo/board_name 2>/dev/null || :)',
                                    '$(printf zbtlink,zbt-we5927)')
        original = original.replace('$(uci -q get veci_sms.main.enabled 2>/dev/null || :)',
                                    '$(printf 1)')
        self.assertNotIn('/etc/veci-sms-'+store_name, original)
        file = root / ('stub-'+name)
        file.write_text(original)
        file.chmod(0o700)
        return file

    def run_helper(self, file, *args, input=None):
        result = subprocess.run(['busybox','ash',str(file),*args],
                                input=input,text=True,capture_output=True,timeout=6)
        self.assertEqual(result.returncode,0,result.stderr)
        return json.loads(result.stdout)

    def test_drafts_are_saved_edited_and_deleted_without_at(self):
        with tempfile.TemporaryDirectory() as td:
            f = self.fixture('drafts', 'drafts', Path(td))
            self.assertNotIn('AT+CMGS', f.read_text())
            self.assertNotIn('AT+CMGD', f.read_text())
            r = self.run_helper(f, '--save','0','-',input=PDU)
            self.assertTrue(r['saved'])
            self.assertEqual(r['id'],1)
            r = self.run_helper(f,'--list')
            self.assertEqual(r['count'],1)
            self.assertEqual(r['drafts'][0]['pdu'],PDU)
            edited = '01'*12
            r = self.run_helper(f,'--save','1',PDU,input=edited)
            self.assertTrue(r['saved'])
            r = self.run_helper(f,'--delete','1',edited)
            self.assertEqual(r['deleted'],1)
            self.assertEqual(self.run_helper(f,'--list')['count'],0)
            self.assertEqual((Path(td)/'drafts').stat().st_mode & 0o777,0o600)

    def test_sent_history_only_after_recording_acceptance(self):
        with tempfile.TemporaryDirectory() as td:
            f = self.fixture('sent-history', 'sent-history',Path(td))
            self.assertNotIn('AT+CMGS', f.read_text())
            self.assertNotIn('AT+CMGD', f.read_text())
            self.assertEqual(self.run_helper(f,'--list')['count'],0)
            self.assertTrue(self.run_helper(f,'--add',input=PDU)['saved'])
            data = self.run_helper(f,'--list')
            self.assertEqual(data['count'],1)
            self.assertEqual(data['messages'][0]['pdu'],PDU)
            self.assertEqual(data['messages'][0]['status'],'accepted_by_modem')

    def test_rpc_full_method_shape_and_fallback(self):
        f=FILES/'rpcd/veci.sms'
        output=subprocess.run(['busybox','ash',str(f),'list'],capture_output=True,
                              text=True,timeout=5,check=True).stdout
        methods=json.loads(output)
        self.assertEqual(set(methods), {
            'getConfig','setEnabled','listMessages','deleteMessage','sendMessage',
            'getSent','getDrafts','saveDraft','deleteDraft'})
        # Without a complete worker bundle, users must not see fake full features.
        output=subprocess.run(['busybox','ash',str(f),'call','getConfig'],
                              capture_output=True,text=True,timeout=5,check=True).stdout
        config=json.loads(output)
        self.assertEqual(config['mode'],'receive_only')

    def test_full_mode_requires_complete_installation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            rpc=(FILES/'rpcd/veci.sms').read_text()
            rpc=rpc.replace('"/usr/libexec/$name"', '"'+tmp+'/$name"')
            rpc=rpc.replace('/usr/libexec/veci-sms-cmgs', tmp+'/veci-sms-cmgs')
            rpc=rpc.replace('/etc/veci-sms-drafts',tmp+'/drafts')
            rpc=rpc.replace('/etc/veci-sms-sent-history',tmp+'/sent-history')
            f=root/'veci.sms'
            f.write_text(rpc)
            f.chmod(0o700)
            def mode():
                proc=subprocess.run(['busybox','ash',str(f),'call','getConfig'],
                                   capture_output=True,text=True,check=True)
                return json.loads(proc.stdout)['mode']
            self.assertEqual(mode(),'receive_only')
            for name in ['veci-sms-delete-one','veci-sms-send-one',
                         'veci-sms-sent-history','veci-sms-drafts','veci-sms-cmgs']:
                worker=root/name
                worker.write_text('#!/bin/sh\nexit 0\n')
                worker.chmod(0o700)
            self.assertEqual(mode(),'receive_only')
            (root/'drafts').touch()
            (root/'sent-history').touch()
            self.assertEqual(mode(),'full')
            (root/'veci-sms-delete-one').unlink()
            self.assertEqual(mode(),'receive_only')

    def test_safety_conditions_before_send_and_delete(self):
        send=(FILES/'veci-sms-send-one').read_text()
        delete=(FILES/'veci-sms-delete-one').read_text()
        rpc=(FILES/'rpcd/veci.sms').read_text()
        for text in (send,delete):
            self.assertIn('ttyUSB2',text)
            self.assertIn(':1.4/ttyUSB2',text)
            self.assertIn('flock -n -x 9',text)
            self.assertIn('AT+CMGF?',text)
            self.assertIn('AT+CMGF=0',text)
            self.assertIn('AT+CMGF=1',text)
        self.assertIn('AT+CMGR=',delete)
        self.assertIn('AT+CMGD=',delete)
        self.assertIn('current" = "$expected',delete)
        self.assertIn('SEND_RATE=',rpc)
        self.assertIn('send_rate_limited',rpc)
        self.assertIn('history_saved',rpc)
        self.assertIn('full_ready',rpc)

if __name__=='__main__':
    unittest.main()
