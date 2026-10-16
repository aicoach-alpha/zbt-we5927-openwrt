"""Offline live-release regression of XL RPC/worker response hotfix.

Uses SHA-pinned real released binary scripts provided by CI, never router/AT.
"""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"scripts/veci-xl-v171-response-hotfix.sh"
OLD_RPC="790dd1f6e1bf95b6cf01d4fdb3c06dbbec1633962be6ef5d8b58f17b38e235aa"
OLD_WORKER="a15f922315e28c5d17fe165b10aed7d100ff87ad392c11f72a52a07b87c6a886"
NEW_RPC="07efdc56e7a346793841980f4c1f00674160d7c1769c934b612c43cc19938f99"
NEW_WORKER="9c7da0a046a65fc800067efd24af5733611f56efa5ffbf5cfecb4662af1e8960"

def sha(path):
 return hashlib.sha256(Path(path).read_bytes()).hexdigest()

@unittest.skipUnless(os.environ.get("VECI_TEST_OLD_RPC") and os.environ.get("VECI_TEST_OLD_WORKER"),"actual release fixture required")
class ResponseHotfix(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  d=self.d=Path(self.tmp.name)
  self.rpc=d/"rpc";self.worker=d/"worker";self.back=d/"backup"
  self.old_rpc=Path(os.environ["VECI_TEST_OLD_RPC"])
  self.old_worker=Path(os.environ["VECI_TEST_OLD_WORKER"])
  self.new_rpc=ROOT/"scripts/veci-xl-ussd-v17-staged/rpcd-veci.ussd"
  self.new_worker=ROOT/"scripts/veci-xl-ussd-v17-staged/veci-xl-ussd"
  for path,expected in [(self.old_rpc,OLD_RPC),(self.old_worker,OLD_WORKER),
                        (self.new_rpc,NEW_RPC),(self.new_worker,NEW_WORKER)]:
   self.assertEqual(sha(path),expected)
  self.rpc.write_bytes(self.old_rpc.read_bytes())
  self.worker.write_bytes(self.old_worker.read_bytes())
  bindir=d/"bin";bindir.mkdir()
  wget=bindir/"wget"
  wget.write_text("""#!/bin/sh
[ "$1" = -qO ] || exit 10
case "$3" in
 */rpcd-veci.ussd) cp "$VECI_TEST_NEW_RPC" "$2" ;;
 */veci-xl-ussd) cp "$VECI_TEST_NEW_WORKER" "$2" ;;
 *)exit 11;;
esac
""")
  wget.chmod(0o700)
  code=SOURCE.read_text()
  for old,new in [
   ("RPC=/usr/libexec/rpcd/veci.ussd","RPC="+str(self.rpc)),
   ("WORKER=/usr/libexec/veci-xl-ussd","WORKER="+str(self.worker)),
   ("BACK=/root/veci-xl-ussd-response-rollback","BACK="+str(self.back)),
   ('[ "$(id -u)" = 0 ]','[ 0 = 0 ]'),
   ('"$(cat /tmp/sysinfo/board_name 2>/dev/null || :)"','"zbtlink,zbt-we5927"'),
  ]:
   self.assertIn(old,code)
   code=code.replace(old,new)
  self.installer=d/"installer";self.installer.write_text(code);self.installer.chmod(0o700)
  self.env=os.environ.copy()
  self.env["PATH"]=str(bindir)+os.pathsep+self.env["PATH"]
  self.env["VECI_TEST_NEW_RPC"]=str(self.new_rpc)
  self.env["VECI_TEST_NEW_WORKER"]=str(self.new_worker)
 def call(self,arg):
  return subprocess.run(["sh",str(self.installer),arg],capture_output=True,
                        text=True,env=self.env,timeout=8)
 def test_apply_and_rollback_exact_files(self):
  c=self.call("apply")
  self.assertEqual(c.returncode,0,c.stdout+c.stderr)
  self.assertIn("VECI_XL_RESPONSE_HOTFIX_LIVE_PASS",c.stdout)
  self.assertEqual(sha(self.rpc),NEW_RPC)
  self.assertEqual(sha(self.worker),NEW_WORKER)
  self.assertEqual(sha(self.back/"rpc"),OLD_RPC)
  self.assertEqual(sha(self.back/"worker"),OLD_WORKER)
  c=self.call("apply")
  self.assertEqual(c.returncode,0,c.stdout+c.stderr)
  self.assertIn("ALREADY_APPLIED_PASS",c.stdout)
  c=self.call("rollback")
  self.assertEqual(c.returncode,0,c.stdout+c.stderr)
  self.assertIn("ROLLBACK_PASS",c.stdout)
  self.assertEqual(sha(self.rpc),OLD_RPC)
  self.assertEqual(sha(self.worker),OLD_WORKER)
 def test_tampered_current_worker_aborts_early(self):
  self.worker.write_text("modified")
  c=self.call("apply")
  self.assertNotEqual(c.returncode,0)
  self.assertIn("unexpected_live_hash",c.stderr)
  self.assertFalse(self.back.exists())
 def test_download_corrupt_does_not_modify_current(self):
  other=self.d/"bad";other.write_text("corrupt")
  self.env["VECI_TEST_NEW_WORKER"]=str(other)
  c=self.call("apply")
  self.assertNotEqual(c.returncode,0)
  self.assertIn("worker_checksum",c.stderr)
  self.assertEqual(sha(self.rpc),OLD_RPC)
  self.assertEqual(sha(self.worker),OLD_WORKER)
  self.assertFalse(self.back.exists())
 def test_tampered_backup_fails_closed(self):
  self.assertEqual(self.call("apply").returncode,0)
  (self.back/"worker").write_text("tampered")
  c=self.call("rollback")
  self.assertNotEqual(c.returncode,0)
  self.assertIn("rollback_failed",c.stderr)
  self.assertEqual(sha(self.rpc),NEW_RPC)

if __name__=="__main__":unittest.main()
