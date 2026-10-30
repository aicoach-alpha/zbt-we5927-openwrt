import pathlib, re, subprocess, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
P=ROOT/'source/veci-app-guest/files/usr/libexec/rpcd/veci.app.guest'
class GuestSettingsSafetyTests(unittest.TestCase):
  def test_shell(self):
    r=subprocess.run(['sh','-n',str(P)],capture_output=True,text=True)
    self.assertEqual(r.returncode,0,r.stderr)
  def test_settings_are_snapshotted_and_fail_closed(self):
    s=P.read_text()
    fn=s.split('method_save() {',1)[1].split('\n}',1)[0]
    for token in ('portal_snapshot_begin','portal_snapshot_restore','guest_settings_snapshot_failed',
      'guest_save_failed_rolled_back','guest_save_rollback_incomplete','portal_snapshot_discard'):
      self.assertIn(token,fn)
    self.assertLess(fn.index('portal_snapshot_begin'),fn.index('save_preferences "$ssid"'))
    self.assertNotIn('wifi reload >/dev/null 2>&1 || true',fn)
  def test_disable_reports_failed(self):
    s=P.read_text()
    self.assertIn('guest_disable_failed',s)
    fn=s.split('disable_portal() {',1)[1].split('\n}',1)[0]
    self.assertIn('[ "$rc" -eq 0 ]',fn)
  def test_pkg_bumped(self):
    self.assertIn('PKG_RELEASE:=4',(ROOT/'source/veci-app-guest/Makefile').read_text())
