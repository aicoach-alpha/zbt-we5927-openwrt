import json
import pathlib
import subprocess
import unittest

BASE = pathlib.Path(__file__).resolve().parents[1]
PKG = BASE / 'source' / 'veci-cellular-we5927'
RPC = PKG / 'files/usr/libexec/rpcd/veci.sms'
PARSER = PKG / 'files/usr/libexec/veci-sms-parse'
ACL = PKG / 'files/usr/share/rpcd/acl.d/veci-cellular-we5927.json'

def parse(raw):
    return subprocess.run(['sh', str(PARSER)], input=raw, text=True,
                          capture_output=True, timeout=3)

class SmsInboxReadOnlyTest(unittest.TestCase):
    def test_parser_with_one_pdu(self):
        r = parse('AT+CMGL=4\r\n+CMGL: 1,0,,7\r\n07919761989900\r\nOK\r\n')
        self.assertEqual(r.returncode, 0, r.stderr)
        obj = json.loads(r.stdout)
        self.assertEqual(obj['count'], 1)
        self.assertEqual(obj['messages'], [{'index':1,'status':0,'pdu':'07919761989900'}])
        self.assertEqual(obj['storage'], 'unknown')

    def test_empty_inbox(self):
        r = parse('AT+CMGL=4\r\nOK\r\n')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)['messages'], [])

    def test_malformed_and_partial_rejected_without_leaking_raw(self):
        examples = [
            'AT+CMGL=4\r\n+CMGL: 1,0,,4\r\nOK\r\n',
            '+CMGL: 1,0,,4\r\n<script>alert(1)</script>\r\nOK\r\n',
            '+CMGL: 1,0,,4\r\n0791976\r\nOK\r\n',
            '+CMGL: 1,0,,4\r\n07919761989900\r\n', # missing terminal OK
            '+CMTI: "SM",1\r\nOK\r\n', # unsolicited modem event
            '+CMGL: 1,0,,4\r\n07919761989900\r\n+CMGL: 1,0,,4\r\n07919761989900\r\nOK\r\n',
        ]
        for raw in examples:
            with self.subTest(raw=raw):
                r = parse(raw)
                self.assertNotEqual(r.returncode, 0)
                self.assertEqual(json.loads(r.stdout), {'ok':False,'error':'invalid_modem_response'})
                self.assertNotIn('<script>', r.stdout)

    def test_sixteen_record_ceiling(self):
        body = '\r\n'.join(f'+CMGL: {n},0,,7\r\n07919761989900' for n in range(16))
        self.assertEqual(json.loads(parse(body+'\r\nOK').stdout)['count'], 16)
        body += '\r\n+CMGL: 16,0,,7\r\n07919761989900'
        self.assertFalse(json.loads(parse(body+'\r\nOK').stdout)['ok'])

    def test_hardened_modem_access_and_no_transaction_mutations(self):
        source = RPC.read_text()
        self.assertIn("*/1-1:1.4/*",source)
        self.assertIn('/dev/ttyUSB3) return 1',source)
        self.assertIn("flock -n -x 9",source)
        self.assertIn("/var/lock/we5927-at.lock",source)
        self.assertIn("'AT+CMGF=0'",source)
        self.assertIn("'AT+CMGF?'",source)
        self.assertIn("'AT+CMGF=1'",source)
        self.assertIn("restore_ok",source)
        self.assertIn("'AT+CMGL=4'",source)
        self.assertNotIn("AT+CMGS",source)
        self.assertNotIn("AT+CMGD",source)
        self.assertNotIn("AT+CUSD=",source)
        self.assertIn("enabled ||",source)
        self.assertIn('head -c 256',source)
        self.assertIn('"mode"',source) if '"mode"' in source else self.assertIn('receive_only',source)
        result = subprocess.run(['sh','-n',str(RPC)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_minimal_ubus_contract_acl_and_package(self):
        d = json.loads(ACL.read_text())['veci-cellular-we5927']
        self.assertEqual(d['read']['ubus']['veci.sms'],['getConfig','listMessages','getSent','getDrafts'])
        self.assertEqual(d['write']['ubus']['veci.sms'],['setEnabled','sendMessage','deleteMessage','saveDraft','deleteDraft'])
        m = PKG.joinpath('Makefile').read_text()
        for marker in ['PKG_RELEASE:=3','/etc/config/veci_sms','/usr/libexec/rpcd/veci.sms','/usr/libexec/veci-sms-parse','veci-sms-send-one','veci-sms-delete-one','veci-sms-drafts','veci-sms-sent-history']:
            self.assertIn(marker,m)
        self.assertTrue(PKG.joinpath('files/etc/config/veci_sms').exists())

if __name__ == '__main__':
    unittest.main()
