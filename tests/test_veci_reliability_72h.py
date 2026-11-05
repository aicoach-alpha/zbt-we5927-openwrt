"""Evidence/rotation tests: every test uses temp dirs, never router or network."""
import os
import pathlib
import subprocess
import tempfile
import time
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
LOGGER=ROOT/'source/we5927-lte/files/usr/sbin/veci-reliability'
PACKAGE=ROOT/'source/we5927-lte/Makefile'

class ReliabilityTest(unittest.TestCase):
 def setup_logger(self,td):
  path=pathlib.Path(td)
  script=LOGGER.read_text()
  script=script.replace('DIR=/overlay/veci-reliability','DIR='+str(path/'persistent'))
  script=script.replace('WIN=/tmp/veci-rel-window','WIN='+str(path/'window'))
  script=script.replace('STATUS=/tmp/veci-rel-status','STATUS='+str(path/'status'))
  local=path/'veci-reliability'
  local.write_text(script)
  local.chmod(0o755)
  (path/'persistent').mkdir()
  return local,path/'persistent',path/'window'

 def run_logger(self,source,*args):
  r=subprocess.run(['busybox','ash',str(source),*args],
      text=True,capture_output=True,timeout=12)
  self.assertEqual(r.returncode,0,r.stderr)
  return r.stdout

 def raw_minute(self,t,up=10000,good=1,wifi=1,boot=None):
  if boot is None:boot=t-up
  return (f'{t},{boot},{up},{good},{good},{wifi},22.5,'
   f'{up*40},{up*20},{up*16},{up*10},2,-62,65.0,'
   f'healthy,ready,12288,0.44\n')

 def test_format_sample_has_18_columns_and_no_identities(self):
  source=LOGGER.read_text()
  for word in ('sms_content','Station MAC','imei','ssid=','password=','AT+CMGS','wifi down','ifdown lte'):
   self.assertNotIn(word,source)
  out=subprocess.run(['busybox','ash',str(LOGGER),'sample'],
       text=True,capture_output=True,timeout=7)
  self.assertEqual(out.returncode,0,out.stderr)
  self.assertEqual(len(out.stdout.strip().split(',')),18)
  self.assertIn('low_disk_free',source)
  self.assertIn('chmod 700 "$DIR"',source)

 def test_five_minute_flush_and_provisional_24h(self):
  with tempfile.TemporaryDirectory() as td:
   source,base,win=self.setup_logger(td)
   now=int(time.time())
   win.write_text(''.join(self.raw_minute(now-240+i*60,10000+i*60) for i in range(5)))
   self.run_logger(source,'flush')
   self.assertEqual(win.stat().st_size,0)
   files=list(base.glob('samples-*.csv'))
   self.assertEqual(len(files),1)
   lines=files[0].read_text().splitlines()
   self.assertEqual(len(lines),2)
   self.assertEqual(len(lines[0].split(',')),21)
   self.assertEqual(len(lines[1].split(',')),21)
   report=self.run_logger(source,'report','24')
   self.assertIn('RESULT=WAITING_FULL_WINDOW',report)
   self.assertIn('INTERNET_ICMP_SUCCESS_PCT=100.00',report)
   self.assertIn('MIN_RAM_AVAILABLE_KB=12288',report)
   self.assertIn('WIFI_PHY_TX_OBSERVED_PEAK_MBPS=65.0',report)
   self.assertIn('SPEED_NOTE=',report)

 def test_complete_72h_and_reboot_count(self):
  with tempfile.TemporaryDirectory() as td:
   source,base,win=self.setup_logger(td)
   now=int(time.time())
   end=now-30; first=end-863*300
   header=LOGGER.read_text().split("HEADER='",1)[1].split("'",1)[0]
   content=[header+'\n']
   for i in range(864):
    t=first+i*300
    up=50000+i*300 if i<400 else 200+(i-400)*300
    boot=t-up
    good=5 if i!=350 else 0
    content.append(f'{t},{boot},{up},5,{good},5,5,24.5,29.0,'
                   '1.2,0.3,4.2,0.8,3,-61,72.2,healthy,ready,12000,0.5,5\n')
   (base/'samples-20261105.csv').write_text(''.join(content))
   report=self.run_logger(source,'report','72')
   self.assertIn('RESULT=ELIGIBLE_FOR_COMPARISON',report)
   self.assertIn('SAMPLES_5M=864',report)
   self.assertIn('REBOOTS_OBSERVED=1',report)
   self.assertIn('WIFI_MAX_STATIONS=3',report)
   self.assertIn('WAN_TRAFFIC_PEAK_RX_MBPS=1.200',report)
   self.assertIn('WIFI_PHY_TX_OBSERVED_PEAK_MBPS=72.2',report)
   # Eligibility only means enough data; never "world fastest".
   self.assertIn('FASTEST_ROUTER_CLAIM=NOT_PROVEN',report)

 def test_sparse_samples_disqualify_72h(self):
  with tempfile.TemporaryDirectory() as td:
   source,base,win=self.setup_logger(td)
   now=int(time.time())
   hdr=LOGGER.read_text().split("HEADER='",1)[1].split("'",1)[0]
   s=[hdr+'\n']
   for i in range(700):
    t=now-259200 + int(i*259000/699)
    s.append(f'{t},12345,20000,5,5,5,5,21.0,25.0,'
             '0.5,0.3,1.0,0.1,1,-65,52.0,healthy,ready,11000,0.3,5\n')
   (base/'samples-20261105.csv').write_text(''.join(s))
   report=self.run_logger(source,'report','72')
   self.assertIn('RESULT=INSUFFICIENT_COVERAGE',report)

 def test_probe_is_bounded_and_no_upload(self):
  s=LOGGER.read_text()
  self.assertIn('head -c 524288',s)
  self.assertIn('21600',s)
  self.assertIn('dev usb0',s)
  self.assertIn('speed.cloudflare.com/__down?bytes=524288',s)
  self.assertNotIn('https://speed.cloudflare.com/__up',s)
  self.assertIn('-mtime +7',s)
  conf=ROOT/'source/we5927-lte/files/etc/config/veci_reliability'
  c=conf.read_text()
  self.assertIn("option interval_seconds '60'",c)
  self.assertIn("option flush_samples '5'",c)
  self.assertIn("option active_download '1'",c)
  m=PACKAGE.read_text()
  self.assertIn('veci-reliability',m)
  init=ROOT/'source/we5927-lte/files/etc/init.d/veci-reliability'
  self.assertIn('USE_PROCD=1',init.read_text())
  for f in (LOGGER,init):
   result=subprocess.run(['sh','-n',str(f)],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__': unittest.main()
