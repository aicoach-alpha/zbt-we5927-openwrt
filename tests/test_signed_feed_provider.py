"""Fail-closed WE5927 signed feed provider, offline tests only."""
import json, os, pathlib, re, subprocess, tempfile, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
PROVIDER=ROOT/'source/veci-app-catalog-we5927/files/usr/libexec/rpcd/veci.apps'
ACL=ROOT/'source/veci-app-catalog-we5927/files/usr/share/rpcd/acl.d/veci-apps.json'
PKG=ROOT/'source/veci-app-catalog-we5927/Makefile'
class SignedFeedProviderTests(unittest.TestCase):
    def test_shell_and_rpcd_method_registry(self):
        r=subprocess.run(['sh','-n',str(PROVIDER)],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        r=subprocess.run(['sh',str(PROVIDER),'list'],capture_output=True,text=True)
        self.assertEqual(json.loads(r.stdout),{'status':{},'verifyFeed':{}})
    def test_bound_install_and_acl(self):
        txt=PKG.read_text()
        self.assertIn('PKG_RELEASE:=2',txt)
        self.assertIn('veci.apps $(1)/usr/libexec/rpcd/veci.apps',txt)
        self.assertIn('veci-apps.json $(1)/usr/share/rpcd/acl.d/veci-apps.json',txt)
        a=json.loads(ACL.read_text())['veci']
        self.assertEqual(a['read']['ubus']['veci.apps'],['status'])
        self.assertEqual(a['write']['ubus']['veci.apps'],['verifyFeed'])
    def test_no_unverified_or_custom_repo_is_trusted(self):
        s=PROVIDER.read_text()
        for token in ('published','https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/app-feed/feeds/',
                      'feed_contract_valid', 'grep -Fxq', 'app_feed_verified_build_id',
                      'apk --keys-dir "$keys_dir" verify', 'verification_stamp_failed',
                      'untrusted_signed_index', 'insufficient_volatile_memory',
                      'uclient-fetch -T 30', '6291456'):
            self.assertIn(token,s)
        self.assertLess(s.index('apk --keys-dir "$keys_dir" verify'),s.index('uci set "veci.main.app_feed_verified_build_id=$id"'))
        for forbidden in ('--allow-untrusted','apk add','apk upgrade','sysupgrade','uci set veci.main.app_feed_enabled=1'):
            self.assertNotIn(forbidden,s)
    def test_absent_firmware_release_returns_fail_closed_status(self):
        s=PROVIDER.read_text()
        with tempfile.TemporaryDirectory() as d:
            t=pathlib.Path(d)
            # The provider must never consult global UCI when immutable release metadata is missing.
            s=s.replace('release_file=/etc/veci-release.json','release_file='+str(t/'absent-release.json'))
            s=s.replace('channel_file=/etc/veci-release-channel','channel_file='+str(t/'absent-channel'))
            s=s.replace('repo_file=/etc/apk/repositories.d/veci-apps.list','repo_file='+str(t/'absent-repo'))
            sh=t/'veci.apps'
            sh.write_text(s)
            status=subprocess.run(['sh',str(sh),'call','status'],text=True,capture_output=True,timeout=8)
            self.assertEqual(status.returncode,0,status.stderr)
            data=json.loads(status.stdout)
            self.assertFalse(data['feed_configured'])
            self.assertFalse(data['feed_verified'])
            self.assertFalse(data['feed_ready'])
            verify=subprocess.run(['sh',str(sh),'call','verifyFeed'],text=True,capture_output=True,timeout=8)
            self.assertEqual(verify.returncode,0,verify.stderr)
            self.assertFalse(json.loads(verify.stdout)['verified'])
    def test_published_contract_requires_signed_indexes_and_no_unverified_stamp(self):
        with tempfile.TemporaryDirectory(prefix='veci-feed-fixture-') as d:
            tmp=pathlib.Path(d)
            bid='0123456789abcdef0123456789abcdef01234567'
            base='https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/app-feed/feeds/'+bid
            release=tmp/'release.json'
            release.write_text(json.dumps({'build_id':bid}))
            channel=tmp/'release-channel';channel.write_text('published\n')
            repo=tmp/'repositories'
            repo.write_text(''.join(base+'/'+x+'\n' for x in (
                'targets/ramips/mt76x8/packages/packages.adb',
                'packages/mipsel_24kc/base/packages.adb',
                'packages/mipsel_24kc/luci/packages.adb',
                'packages/mipsel_24kc/packages/packages.adb')))
            keys=tmp/'keys';keys.mkdir()
            (keys/'trusted.pem').write_text('FAKE_TEST_ONLY')
            txt=PROVIDER.read_text()
            for original,replacement in (
                ('release_file=/etc/veci-release.json', 'release_file='+str(release)),
                ('repo_file=/etc/apk/repositories.d/veci-apps.list','repo_file='+str(repo)),
                ('channel_file=/etc/veci-release-channel','channel_file='+str(channel)),
                ('keys_dir=/etc/apk/keys','keys_dir='+str(keys)),
                ('lock=/tmp/veci-app-feed-verify.lock','lock='+str(tmp/'lock')),
                ('/tmp/veci-app-feed.XXXXXX',str(tmp/'temp.XXXXXX'))):
                txt=txt.replace(original,replacement)
            script=tmp/'veci.apps';script.write_text(txt)
            bindir=tmp/'bin';bindir.mkdir()
            def fake(name,scripttext):
                f=bindir/name;f.write_text('#!/bin/sh\n'+scripttext);f.chmod(0o755)
            fake('jsonfilter','echo '+bid+'\n')
            fake('uci',"""case "$1" in
  set) touch "$MOCK_STAMP";;
  commit) :;;
  *) case "$*" in
      *app_feed_build_id*) echo 0123456789abcdef0123456789abcdef01234567;;
      *app_feed_enabled*) echo 1;;
      *app_feed_verified_build_id*) :;;
     esac;;
esac
""")
            fake('df',"printf 'Filesystem 1024-blocks Used Available Capacity Mounted on\\n'; printf 'tmpfs 131072 2048 129024 1%% /overlay\\n'\n")
            fake('uclient-fetch','printf "%0250d\\n" 0 > "$4"\n')
            fake('apk','test "$MOCK_SIGNATURE_FAIL" != 1\n')
            env={**os.environ,'PATH':str(bindir)+':'+os.environ['PATH'],'MOCK_STAMP':str(tmp/'stamp'),
                 'MOCK_SIGNATURE_FAIL':'1'}
            status=subprocess.run(['sh',str(script),'call','status'],capture_output=True,text=True,env=env,timeout=8)
            parsed=json.loads(status.stdout)
            self.assertTrue(parsed['feed_configured'])
            self.assertFalse(parsed['feed_verified'])
            self.assertFalse(parsed['feed_ready'])
            invalid=subprocess.run(['sh',str(script),'call','verifyFeed'],capture_output=True,text=True,env=env,timeout=8)
            self.assertEqual(invalid.returncode,0,invalid.stderr)
            self.assertFalse(json.loads(invalid.stdout)['verified'])
            self.assertFalse((tmp/'stamp').exists())
            env['MOCK_SIGNATURE_FAIL']='0'
            valid=subprocess.run(['sh',str(script),'call','verifyFeed'],capture_output=True,text=True,env=env,timeout=8)
            self.assertEqual(valid.returncode,0,valid.stderr)
            self.assertTrue(json.loads(valid.stdout)['verified'])
            self.assertTrue((tmp/'stamp').is_file())
            self.assertFalse((tmp/'lock').exists())
            # Even successfully signed indexes must never make a changed endpoint trusted.
            repo.write_text(repo.read_text().replace('raw.githubusercontent.com','untrusted.example'))
            denied=subprocess.run(['sh',str(script),'call','verifyFeed'],capture_output=True,text=True,env=env,timeout=8)
            self.assertFalse(json.loads(denied.stdout)['verified'])
    def test_no_credentials_or_private_keys_exported(self):
        s=PROVIDER.read_text()
        self.assertNotIn('cat "$keys_dir"',s)
        self.assertNotIn('cat /etc/shadow',s)
        self.assertNotIn('password=',s)
if __name__=='__main__':unittest.main()
