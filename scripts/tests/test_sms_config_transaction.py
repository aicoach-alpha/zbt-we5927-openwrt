"""Isolated native UCI SMS enable/disable; no modem access."""
import fcntl,json,os,subprocess,tempfile,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[2]/"source/veci-cellular-we5927/files/usr/libexec/rpcd/veci.sms"
UCI=os.environ.get("VECI_HOST_UCI","")
@unittest.skipUnless(Path(UCI).is_file(),"native UCI required")
class SmsConfig(unittest.TestCase):
 def test_lifecycle_lock_and_rollback(self):
  with tempfile.TemporaryDirectory() as t:
   d=Path(t);(d/"config").mkdir();(d/"delta").mkdir()
   cfg=d/"config/veci_sms";cfg.write_text("config sms 'main'\n option enabled '0'\n")
   lock=d/"lock"
   p=d/"provider";p.write_text(P.read_text().replace("/etc/config/veci_sms",str(cfg)).replace("/var/lock/veci-sms-inbox-rpc.lock",str(lock)))
   u=d/"uci";u.write_text(f'#!/bin/sh\nexec "{UCI}" -c "{d}/config" -t "{d}/delta" "$@"\n');u.chmod(0o700)
   j=d/"jsonfilter";j.write_text('#!/usr/bin/env python3\nimport json,sys;print(json.load(sys.stdin)["state"])\n');j.chmod(0o700)
   env=dict(os.environ,PATH=str(d)+":"+os.environ["PATH"])
   def call(method,**kw):
    r=subprocess.run(["busybox","ash",str(p),"call",method],input=json.dumps(kw),text=True,capture_output=True,timeout=5,env=env)
    self.assertEqual(r.returncode,0,r.stderr);return json.loads(r.stdout)
   before=cfg.read_bytes()
   with lock.open("w") as h:
    fcntl.flock(h,fcntl.LOCK_EX)
    self.assertEqual(call("setEnabled",state="on")["error"],"modem_busy")
    self.assertEqual(call("listMessages")["error"],"modem_busy")
   self.assertFalse(call("getConfig")["enabled"])
   self.assertFalse(call("setEnabled",state="invalid")["ok"])
   self.assertEqual(cfg.read_bytes(),before)
   original=u.read_text()
   u.write_text(original.replace('exec "', '"',1)+'rc=$?\ncase "$*" in *"commit veci_sms") exit 1;; esac\nexit "$rc"\n')
   self.assertEqual(call("setEnabled",state="on")["error"],"save_failed")
   self.assertEqual(cfg.read_bytes(),before)
   u.write_text(original)
   self.assertTrue(call("setEnabled",state="on")["enabled"])
   snapshot=cfg.read_bytes();self.assertTrue(call("setEnabled",state="on")["enabled"])
   self.assertEqual(cfg.read_bytes(),snapshot)
   self.assertFalse(call("setEnabled",state="off")["enabled"])
