"""Prevent install offers and both apply paths without authorized policy."""
from pathlib import Path
import json,unittest,subprocess
ROOT=Path(__file__).resolve().parents[2]
R=ROOT/'rebuild/veci-v2/packages/veci-v2-runtime'
U=ROOT/'rebuild/veci-v2/packages/veci-v2-ui'
class VerifyOnlyDefault(unittest.TestCase):
    def test_policy_default_and_fail_closed_cgi(self):
        self.assertEqual((R/'update-policy.default').read_text(),'verify_only\n')
        cgi=(U/'files/www/cgi-bin/veci2-verify').read_text()
        self.assertIn('[ "$operation" = apply ] && [ "$allow_install" != true ]',cgi)
        self.assertIn('installation_locked',cgi)
        self.assertIn('install_allowed',cgi)
        self.assertIn('stable-apply) ota=true; operation=apply',cgi)
        self.assertIn('sysupgrade "$work/image"',cgi)
        frontend=(U/'files/www/veci2/app.js').read_text()
        self.assertIn('if (receipt.install_allowed !== true) return;',frontend)
        self.assertIn('clearInstallCandidate();',frontend)
    def test_admin_scoped_policy_and_scripts(self):
        acl=json.loads((R/'veci2-status-acl.json').read_text())
        policy=acl['veci-v2-firmware-policy']
        self.assertEqual(policy['read']['ubus']['veci.v2.updatepolicy'],['status'])
        self.assertEqual(policy['write']['ubus']['veci.v2.updatepolicy'],['save'])
        script=(R/'veci2-update-policy').read_text()
        self.assertIn('upgrade_busy',script)
        self.assertIn('verify_only',script)
        for p in (R/'veci2-update-policy',U/'files/www/cgi-bin/veci2-verify'):
            subprocess.run(['sh','-n',str(p)],check=True,capture_output=True)
if __name__=='__main__':unittest.main()
