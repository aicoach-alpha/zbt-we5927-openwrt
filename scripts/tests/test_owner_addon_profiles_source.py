"""Check profile toggles use existing service and UCI, not duplicate daemons."""
import json,subprocess,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
R=ROOT/'rebuild/veci-v2/packages/veci-v2-runtime'
U=ROOT/'rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2'
class AddonProfiles(unittest.TestCase):
    def test_read_and_write_acl_exact_and_guarded(self):
        acl=json.loads((R/'veci2-addon-acl.json').read_text())
        group=acl['veci-v2-addon-admin']
        self.assertEqual(group['read']['ubus']['veci.v2.addon'], ['status'])
        self.assertEqual(group['write']['ubus']['veci.v2.addon'], ['setVpnStartup'])
        helper=(R/'veci2-addon-profiles').read_text()
        self.assertIn('stale_selection',helper)
        self.assertIn('ENABLE_WIREGUARD_NEXT_BOOT',helper)
        self.assertIn('uci -q -t "$tmp" commit network',helper)
        self.assertNotIn('service_restart',helper)
        self.assertNotIn('network restart',helper)
    def test_existing_daemon_reused(self):
        service=(R/'veci2-addon').read_text()
        self.assertIn('/usr/libexec/veci2-addon-profiles',service)
        self.assertIn('setVpnStartup',service)
        self.assertIn('profile_status',service)
        for fn in ('veci2-addon','veci2-addon-profiles'):
            subprocess.run(['sh','-n',str(R/fn)],check=True)
        s=(U/'addon-profiles.js').read_text()
        self.assertIn('window.confirm',s)
        self.assertIn('veci.v2.addon',s)
        subprocess.run(['node','--check',str(U/'addon-profiles.js')],check=True)
        html=(U/'index.html').read_text()
        self.assertIn('id="addon-profiles-read"',html)
        self.assertIn('addon-profiles.js',html)
if __name__=='__main__':unittest.main()
