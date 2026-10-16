"""rpcd exec-plugin must return exactly one JSON object on worker failure.

No carrier, modem or network access. Simulates byte-accurate child output.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE=Path(__file__).resolve().parents[1]/"scripts/veci-xl-ussd-v17-staged/rpcd-veci.ussd"

class XLUSSDRPCContract(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.addCleanup(self.tmp.cleanup)
  d=self.d=Path(self.tmp.name)
  bindir=d/"bin";bindir.mkdir()
  jf=bindir/"jsonfilter"
  jf.write_text("""#!/usr/bin/env python3
import json,sys
try:
 a=sys.argv
 s=a[a.index('-s')+1]
 key=a[a.index('-e')+1].removeprefix('@.')
 v=json.loads(s)[key]
 print(str(v).lower() if isinstance(v,bool) else v)
except Exception:
 sys.exit(1)
""")
  jf.chmod(0o700)
  self.worker=d/"worker"
  self.worker.write_text("""#!/bin/sh
cat "$MOCK_RESULT"
exit "$(cat "$MOCK_EXIT")"
""")
  self.worker.chmod(0o700)
  self.reply=d/"reply"
  self.exitcode=d/"exitcode"
  self.reply.write_text('{"ok":false,"reason":"wrong_modem"}\n')
  self.exitcode.write_text("1\n")
  code=SOURCE.read_text()
  self.assertIn("emit",code)
  code=code.replace("RUN=/usr/libexec/veci-xl-ussd","RUN="+str(self.worker))
  code=code.replace('[ "$(id -u)" = 0 ]','[ 0 = 0 ]')
  self.rpc=d/"rpc";self.rpc.write_text(code);self.rpc.chmod(0o700)
  self.env=os.environ.copy()
  self.env["PATH"]=str(bindir)+os.pathsep+self.env["PATH"]
  self.env["MOCK_RESULT"]=str(self.reply)
  self.env["MOCK_EXIT"]=str(self.exitcode)
 def run_start(self):
  return subprocess.run(["sh",str(self.rpc),"call","start"],input="{}",
      text=True,capture_output=True,env=self.env,timeout=5)
 def test_worker_error_is_one_valid_json(self):
  cp=self.run_start()
  self.assertEqual(cp.returncode,0,cp.stderr)
  self.assertEqual(json.loads(cp.stdout),{"ok":False,"reason":"wrong_modem"})
  self.assertEqual(cp.stdout.count("\n"),1)
 def test_worker_success_is_one_valid_json(self):
  self.reply.write_text('{"ok":true,"source":"operator_ussd","mode":0,"dcs":15,"text_supported":true,"interactive":false,"text":"Sisa Kuota 1 GB","session":"abc"}\n')
  self.exitcode.write_text("0\n")
  cp=self.run_start()
  self.assertEqual(cp.returncode,0,cp.stderr)
  self.assertTrue(json.loads(cp.stdout)["ok"])
  self.assertEqual(cp.stdout.count("\n"),1)
 def test_worker_empty_failure_gets_structured_error(self):
  self.reply.write_text("")
  cp=self.run_start()
  self.assertEqual(cp.returncode,0,cp.stderr)
  self.assertEqual(json.loads(cp.stdout),{"ok":False,"reason":"ussd_unavailable"})
 def test_worker_multi_object_failure_never_leaks_double_json(self):
  self.reply.write_text('{"ok":false,"reason":"wrong_modem"}\n{"ok":false,"reason":"unavailable"}\n')
  cp=self.run_start()
  self.assertEqual(cp.returncode,0,cp.stderr)
  self.assertEqual(json.loads(cp.stdout),{"ok":False,"reason":"invalid_response"})
  self.assertEqual(cp.stdout.count("\n"),1)
 def test_worker_error_cannot_inject_newline_or_sensitive_logs(self):
  self.reply.write_text('{"ok":false,"reason":"wrong_modem\\\\nSECRET"}\n')
  cp=self.run_start()
  self.assertEqual(cp.returncode,0,cp.stderr)
  self.assertEqual(json.loads(cp.stdout),{"ok":False,"reason":"invalid_response"})
  self.assertNotIn("SECRET",cp.stdout+cp.stderr)

if __name__=="__main__":unittest.main()
