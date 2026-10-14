"""Mock actual GitHub v1.7.1 worker hotfix without touching router or network."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"scripts/veci-xl-v171-nood-hotfix.sh"
OLD_SHA="7a8a8d0a64ebb1fd5e74bf7eff069ee3bae05fc3fdfc544b7e99d481a1050fea"
NEW_SHA="a15f922315e28c5d17fe165b10aed7d100ff87ad392c11f72a52a07b87c6a886"
OLD=os.environ.get("VECI_TEST_OLD")
NEW=os.environ.get("VECI_TEST_NEW")
@unittest.skipUnless(OLD and NEW,"Only run in pinned release fixture CI")
class Hotfix(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory()
  self.addCleanup(self.temp.cleanup)
  d=self.d=Path(self.temp.name)
  self.target=d/"veci-xl-ussd"
  self.back=d/"backup"
  self.target.write_bytes(Path(OLD).read_bytes())
  assert hashlib.sha256(self.target.read_bytes()).hexdigest()==OLD_SHA
  assert hashlib.sha256(Path(NEW).read_bytes()).hexdigest()==NEW_SHA
  b=d/"bin";b.mkdir()
  wget=b/"wget"
  wget.write_text('''#!/bin/sh
[ "$1" = -qO ] || exit 2
cp "$VECI_TEST_NEW" "$2"
''')
  wget.chmod(0o700)
  content=SRC.read_text()
  for a,b in [
    ("TARGET=/usr/libexec/veci-xl-ussd","TARGET="+str(self.target)),
    ("BACK=/root/veci-xl-ussd-nood-rollback","BACK="+str(self.back)),
    ('[ "$(id -u)" = 0 ]','[ 0 = 0 ]'),
    ('"$(cat /tmp/sysinfo/board_name 2>/dev/null || :)"','"zbtlink,zbt-we5927"'),
  ]:
   self.assertIn(a,content)
   content=content.replace(a,b)
  self.worker=d/"hotfix"
  self.worker.write_text(content)
  self.worker.chmod(0o700)
  self.env=os.environ.copy()
  self.env["PATH"]=str(d/"bin")+os.pathsep+self.env["PATH"]
 def call(self,arg):
  return subprocess.run(["sh",str(self.worker),arg],capture_output=True,text=True,
                        env=self.env,timeout=6)
 def test_apply_rollback_roundtrip(self):
  p=self.call("apply")
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
  self.assertIn("VECI_XL_OD_HOTFIX_LIVE_PASS",p.stdout)
  self.assertEqual(hashlib.sha256(self.target.read_bytes()).hexdigest(),NEW_SHA)
  self.assertEqual(hashlib.sha256(self.back.read_bytes()).hexdigest(),OLD_SHA)
  p=self.call("apply")
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
  self.assertIn("ALREADY_APPLIED_PASS",p.stdout)
  p=self.call("rollback")
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
  self.assertIn("VECI_XL_OD_HOTFIX_ROLLBACK_PASS",p.stdout)
  self.assertEqual(hashlib.sha256(self.target.read_bytes()).hexdigest(),OLD_SHA)
 def test_unknown_live_file_denied(self):
  self.target.write_text("tampered")
  p=self.call("apply")
  self.assertNotEqual(p.returncode,0)
  self.assertIn("unknown_live_worker",p.stderr)
  self.assertFalse(self.back.exists())
 def test_invalid_download_leaves_live_unchanged(self):
  self.env["VECI_TEST_NEW"]=str(self.d/"bad")
  (self.d/"bad").write_text("ATTACK")
  p=self.call("apply")
  self.assertNotEqual(p.returncode,0)
  self.assertIn("checksum_mismatch",p.stderr)
  self.assertEqual(hashlib.sha256(self.target.read_bytes()).hexdigest(),OLD_SHA)
  self.assertFalse(self.back.exists())
 def test_tampered_rollback_refused(self):
  self.assertEqual(self.call("apply").returncode,0)
  self.back.write_text("tampered backup")
  p=self.call("rollback")
  self.assertNotEqual(p.returncode,0)
  self.assertIn("backup_invalid",p.stderr)
  self.assertEqual(hashlib.sha256(self.target.read_bytes()).hexdigest(),NEW_SHA)
if __name__=="__main__":
 unittest.main()
