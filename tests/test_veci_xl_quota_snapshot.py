"""Volatile XL quota only from explicit operator USSD response; no carrier I/O."""
import json
import os
import pathlib
import subprocess
import tempfile
import time
import unittest

SRC=pathlib.Path(__file__).resolve().parents[1]/"scripts/veci-xl-ussd-v17-staged/veci-xl-quota-cache"
class Cache(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.d=pathlib.Path(self.tmp.name)
  self.file=self.d/"quota"
  self.bin=self.d/"bin";self.bin.mkdir()
  mock=self.bin/"jsonfilter"
  mock.write_text("""#!/usr/bin/env python3
import json,sys
try:
 a=sys.argv
 s=a[a.index('-s')+1]
 key=a[a.index('-e')+1]
 result=json.loads(s)[key.removeprefix('@.')]
 print(str(result).lower() if isinstance(result,bool) else result)
except Exception:sys.exit(1)
""")
  mock.chmod(0o700)
  content=SRC.read_text()
  content=content.replace('FILE=/tmp/veci-xl-quota.state','FILE='+str(self.file))
  content=content.replace('[ "$(id -u)" = 0 ]','[ 0 = 0 ]')
  content=content.replace('"-rw-------:0"','"-rw-------:'+str(os.getuid())+'"')
  self.script=self.d/"worker";self.script.write_text(content)
  self.script.chmod(0o700)
  self.env=os.environ.copy()
  self.env['PATH']=str(self.bin)+os.pathsep+self.env.get('PATH','')
 def tearDown(self):self.tmp.cleanup()
 def send(self,text):
  j={"ok":True,"source":"operator_ussd","mode":0,"dcs":15,
     "text_supported":True,"interactive":False,"text":text}
  return subprocess.run(['sh',str(self.script),'--record'],
      input=json.dumps(j,separators=(',',':')),text=True,capture_output=True,
      env=self.env,timeout=4)
 def status(self):
  r=subprocess.run(['sh',str(self.script),'--status'],capture_output=True,
      text=True,env=self.env,timeout=4)
  self.assertEqual(r.returncode,0,r.stderr)
  return json.loads(r.stdout)
 def test_empty_not_checked(self):
  o=self.status()
  self.assertEqual(o['state'],'not_checked')
  self.assertIsNone(o['remaining_display'])
 def test_exact_remaining_from_operator(self):
  r=self.send('Paket aktif. Sisa Kuota: 1,5 GB. Aktif sampai 21 Okt.')
  self.assertEqual(r.returncode,0,r.stdout+r.stderr)
  o=self.status()
  self.assertEqual(o['state'],'ready')
  self.assertEqual(o['source'],'operator_ussd')
  self.assertEqual(o['remaining_display'],'1,5 GB')
  self.assertIsNone(o['total_display'])
  self.assertNotIn('Paket aktif',self.file.read_text())
  self.assertNotIn('Aktif sampai',self.file.read_text())
 def test_unknown_or_promo_never_overwrites(self):
  self.assertEqual(self.send('Sisa Kuota 200 MB').returncode,0)
  for text in ['Beli promo sisa kuota 500 GB', 'Kuota awal 10 GB',
               'Silakan aktivasi paket 10 GB', 'Saldo Rp 12000']:
   self.assertNotEqual(self.send(text).returncode,0)
   self.assertEqual(self.status()['remaining_display'],'200 MB')
 def test_expiry(self):
  self.assertEqual(self.send('Sisa Kuota: 512 KB').returncode,0)
  a=self.file.read_text().split('|')
  a[0]=str(int(time.time())-901)
  self.file.write_text('|'.join(a))
  self.assertEqual(self.status()['state'],'stale')
 def test_future_timestamp_fails_closed(self):
  self.assertEqual(self.send('Sisa Kuota: 512 MB').returncode,0)
  self.file.write_text(str(int(time.time())+100)+'|512|MB\n')
  self.assertEqual(self.status()['state'],'stale')
 def test_no_sms_or_network_fetch_code(self):
  s=SRC.read_text()
  for bad in ('AT+CMGR','AT+CMGL','AT+CMGS','curl ','wget ','my.xl.co.id'):
   self.assertNotIn(bad,s)
  self.assertEqual(subprocess.run(['sh','-n',str(SRC)]).returncode,0)
if __name__=='__main__':unittest.main()
