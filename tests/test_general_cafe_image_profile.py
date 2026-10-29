import json, os, pathlib, subprocess, tempfile, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
PROFILE=ROOT/'scripts/prepare-veci-general-cafe-profile.sh'
VERIFY=ROOT/'scripts/verify-veci-general-cafe-image.sh'
NEEDED=('uspot','uspot-www','veci-app-guest','veci-app-voucher')
CORE=('veci','veci-default-ui','veci-cellular-we5927','veci-app-catalog-we5927','veci-update-we5927')
BASIC=('kernel','base-files','dropbear','rpcd','uhttpd','dnsmasq','firewall4','netifd','we5927-lte')
class CafeProfileTests(unittest.TestCase):
    def test_shell_syntax_and_no_live_commands(self):
        for f in (PROFILE,VERIFY):
            p=subprocess.run(['sh','-n',str(f)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            text=f.read_text()
            for action in ('sysupgrade ', 'apk add ', 'apk del ', 'uci set ', 'uci commit ',
                           '/etc/init.d/', 'wifi reload'):
                self.assertNotIn(action,text)
        self.assertIn('7808 * 1024',VERIFY.read_text())

    def fixture_tree(self,top,board=True,signed=True):
        r=pathlib.Path(top)/'openwrt'
        for sub in ('scripts','package/veci-app-voucher'):
            (r/sub).mkdir(parents=True)
        (r/'rules.mk').write_text('dummy=1\n')
        (r/'scripts/feeds').write_text('#!/bin/sh\n')
        (r/'scripts/feeds').chmod(0o755)
        (r/'package/veci-app-voucher/Makefile').write_text('PKG_NAME:=veci-app-voucher\n')
        cfg=['CONFIG_PACKAGE_'+x+'=y' for x in CORE]
        cfg.extend(['CONFIG_TARGET_ramips_mt76x8_DEVICE_zbtlink_zbt-we5927='+('y' if board else 'n'),
                    'CONFIG_SIGNED_PACKAGES='+('y' if signed else 'n'),
                    '# CONFIG_PACKAGE_uspot is not set',
                    '# CONFIG_PACKAGE_uspot-www is not set',
                    'CONFIG_PACKAGE_veci-app-guest=m',
                    '# CONFIG_PACKAGE_veci-app-voucher is not set',
                    'CONFIG_PACKAGE_we5927-lte=y',
                    'CONFIG_PACKAGE_kmod-usb-net-rndis=y'])
        (r/'.config').write_text('\n'.join(cfg)+'\n')
        bindir=pathlib.Path(top)/'mockbin'
        bindir.mkdir()
        make=bindir/'make'
        make.write_text('#!/bin/sh\nexit 0\n');make.chmod(0o755)
        return r, {'PATH':str(bindir)+':'+os.environ['PATH']}

    def test_profile_enables_native_dependencies_and_preserves_lte(self):
        with tempfile.TemporaryDirectory() as d:
            tree,env=self.fixture_tree(d)
            for _ in range(2):
                p=subprocess.run(['sh',str(PROFILE),str(tree)],capture_output=True,text=True,env=env)
                self.assertEqual(p.returncode,0,p.stderr)
            data=(tree/'.config').read_text()
            for pkg in NEEDED:
                self.assertEqual(data.count('CONFIG_PACKAGE_'+pkg+'=y'),1,pkg)
            self.assertIn('CONFIG_PACKAGE_kmod-usb-net-rndis=y',data)
            self.assertIn('CONFIG_PACKAGE_we5927-lte=y',data)
            self.assertIn('CONFIG_SIGNED_PACKAGES=y',data)

    def test_wrong_board_and_unsigned_fails_closed(self):
        for named,variant in (('board',dict(board=False)),('signing',dict(signed=False))):
            with self.subTest(named=named), tempfile.TemporaryDirectory() as d:
                tree,env=self.fixture_tree(d,**variant)
                old=(tree/'.config').read_bytes()
                p=subprocess.run(['sh',str(PROFILE),str(tree)],capture_output=True,text=True,env=env)
                self.assertNotEqual(p.returncode,0)
                self.assertEqual((tree/'.config').read_bytes(),old)

    def fixture_image(self,dir):
        d=pathlib.Path(dir)
        image=d/'sysupgrade.bin'
        image.write_bytes(b'a'*1048576)
        manifest=d/'image.manifest'
        manifest.write_text(''.join(x+' - 1.0-r1\n' for x in (*BASIC,*CORE,*NEEDED)))
        fwtool=d/'fwtool'
        fwtool.write_text("""#!/bin/sh
cat > "$2" <<EOF
{"supported_devices":["zbtlink,zbt-we5927"],"version":{"target":"ramips/mt76x8"}}
EOF
""")
        fwtool.chmod(0o755)
        return image,manifest,fwtool

    def test_good_candidate_is_still_not_flash_authorized(self):
        with tempfile.TemporaryDirectory() as d:
            image,manifest,fwtool=self.fixture_image(d)
            p=subprocess.run(['sh',str(VERIFY),str(image),str(manifest),str(fwtool)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn('FLASH_DECISION=NO_GO',p.stdout)
            self.assertIn('BUNDLED_APPS_AND_ROUTER_CORE=PASS',p.stdout)

    def test_reject_missing_deps(self):
        with tempfile.TemporaryDirectory() as d:
            image,manifest,fwtool=self.fixture_image(d)
            manifest.write_text(manifest.read_text().replace('uspot-www - 1.0-r1\n',''))
            p=subprocess.run(['sh',str(VERIFY),str(image),str(manifest),str(fwtool)],capture_output=True,text=True)
            self.assertNotEqual(p.returncode,0)
            self.assertIn('uspot-www',p.stderr+p.stdout)

    def test_reject_oversize(self):
        with tempfile.TemporaryDirectory() as d:
            image,manifest,fwtool=self.fixture_image(d)
            with image.open('wb') as f: f.truncate(7808*1024+1)
            p=subprocess.run(['sh',str(VERIFY),str(image),str(manifest),str(fwtool)],capture_output=True,text=True)
            self.assertNotEqual(p.returncode,0)
            self.assertIn('firmware size',p.stderr)

    def test_reject_wrong_device_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            image,manifest,fwtool=self.fixture_image(d)
            fwtool.write_text(fwtool.read_text().replace('zbtlink,zbt-we5927','other-router'))
            p=subprocess.run(['sh',str(VERIFY),str(image),str(manifest),str(fwtool)],capture_output=True,text=True)
            self.assertNotEqual(p.returncode,0)
            self.assertIn('board/target',p.stderr+p.stdout)

    def test_archived_october_image_rejected_for_missing_cafe_dependencies(self):
        archived=ROOT/'releases/v2026.10.06'
        image=archived/'openwrt-25.12.5-zbt-we5927-v2026.10.06-sysupgrade.bin'
        manifest=archived/'openwrt-25.12.5-zbt-we5927-v2026.10.06.manifest'
        metadata=archived/'sysupgrade-meta.json'
        self.assertTrue(image.is_file())
        self.assertTrue(manifest.is_file())
        with tempfile.TemporaryDirectory() as d:
            fwtool=pathlib.Path(d)/'mock-fwtool'
            fwtool.write_text('#!/bin/sh\ncp '+str(metadata)+' "$2"\n')
            fwtool.chmod(0o755)
            r=subprocess.run(['sh',str(VERIFY),str(image),str(manifest),str(fwtool)],
                             capture_output=True,text=True,timeout=12)
            self.assertNotEqual(r.returncode,0)
            self.assertIn('STOP: missing firmware packages',r.stdout+r.stderr)
            self.assertIn('uspot',r.stdout+r.stderr)

if __name__=='__main__': unittest.main()
