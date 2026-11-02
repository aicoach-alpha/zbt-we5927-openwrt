import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]


class FailClosedPreRemoveTests(unittest.TestCase):
    def run_case(self, name, response='{"ok":true}', ubus_exit=0,
                 voucher_installed=False, cleaner_exit=0):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d)
            fake=root/'bin'
            fake.mkdir()
            audit=root/'actions'
            def script(name,content):
                target=fake/name
                target.write_text(content)
                target.chmod(0o755)
            script('ubus',"""#!/bin/sh
printf 'ubus:%s\\n' "$*" >> "$AUDIT"
printf '%s\\n' "$UBUS_RESPONSE"
exit "$UBUS_EXIT"
""")
            script('jsonfilter',"""#!/bin/sh
IFS= read -r reply || [ -n "$reply" ] || exit 1
case "$reply" in
  '{"ok":true}') printf 'true\\n';;
  '{"ok":false}') printf 'false\\n';;
  '{}') printf '\\n';;
  *) exit 1;;
esac
""")
            script('apk',"""#!/bin/sh
printf 'apk:%s\\n' "$*" >> "$AUDIT"
if [ "$APK_VOUCHER_INSTALLED" = yes ]; then exit 0; fi
exit 1
""")
            script('veci-voucher-cleaner',"""#!/bin/sh
printf 'cleaner:%s\\n' "$*" >> "$AUDIT"
exit "$CLEANER_EXIT"
""")
            source=(ROOT/f'source/veci-app-{name}/files/usr/libexec/veci/{name}-prerm').read_text()
            # Redirect absolute service paths only in the unit-test process, so
            # no real NAS service is ever called.
            source=source.replace('/etc/init.d/veci-voucher-cleaner','veci-voucher-cleaner')
            env={**os.environ,'PATH':str(fake)+':'+os.environ.get('PATH',''),
                 'AUDIT':str(audit),'UBUS_RESPONSE':response,
                 'UBUS_EXIT':str(ubus_exit),
                 'APK_VOUCHER_INSTALLED':'yes' if voucher_installed else 'no',
                 'CLEANER_EXIT':str(cleaner_exit)}
            done=subprocess.run(['sh','-c',source],capture_output=True,text=True,env=env,timeout=8)
            return done, audit.read_text().splitlines() if audit.exists() else []

    def test_shell_syntax_and_package_integration(self):
        for name,release in [('guest','5'),('voucher','4')]:
            with self.subTest(name=name):
                helper=ROOT/f'source/veci-app-{name}/files/usr/libexec/veci/{name}-prerm'
                build=(ROOT/f'source/veci-app-{name}/Makefile').read_text()
                self.assertEqual(subprocess.run(['sh','-n',str(helper)]).returncode,0)
                self.assertIn('PKG_RELEASE:='+release,build)
                self.assertIn('./files/usr/libexec/veci/'+name+'-prerm',build)
                self.assertIn('/usr/libexec/veci/'+name+'-prerm',build)
                self.assertIn('IPKG_INSTROOT',build)
                self.assertNotIn("cleanup '{}' >/dev/null 2>&1 || true",build)

    def test_cleanup_error_fail_closes(self):
        for name in ('guest','voucher'):
            for result in ('{"ok":false}', '{}', 'invalid-json'):
                with self.subTest(name=name,result=result):
                    run,actions=self.run_case(name,response=result)
                    self.assertNotEqual(run.returncode,0)
                    self.assertIn('ubus:call veci.app.'+name+" cleanup {}",actions)
                    self.assertFalse(any(x.startswith('cleaner:') for x in actions))

    def test_rpc_unavailable_fail_closes(self):
        for name in ('guest','voucher'):
            with self.subTest(name=name):
                run,actions=self.run_case(name,ubus_exit=7)
                self.assertNotEqual(run.returncode,0)
                self.assertFalse(any(x.startswith('cleaner:') for x in actions))

    def test_guest_cannot_be_removed_while_voucher_installed(self):
        run,actions=self.run_case('guest',voucher_installed=True)
        self.assertNotEqual(run.returncode,0)
        self.assertFalse(any(x.startswith('ubus:') for x in actions))

    def test_guest_cleanup_success(self):
        run,actions=self.run_case('guest')
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertIn('ubus:call veci.app.guest cleanup {}',actions)

    def test_voucher_cleanup_success_stops_cleaner_after_rpc(self):
        run,actions=self.run_case('voucher')
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertEqual(actions,[
            'ubus:call veci.app.voucher cleanup {}',
            'cleaner:stop','cleaner:disable'
        ])

    def test_voucher_service_stop_failure_blocks_removal(self):
        run,actions=self.run_case('voucher',cleaner_exit=1)
        self.assertNotEqual(run.returncode,0)
        self.assertNotIn('cleaner:disable',actions)

    def test_no_impermissible_fallback_or_direct_uci(self):
        for name in ('guest','voucher'):
            content=(ROOT/f'source/veci-app-{name}/files/usr/libexec/veci/{name}-prerm').read_text()
            for bad in ('|| true','uci set ','uci commit ','sysupgrade','apk del '):
                self.assertNotIn(bad,content)

if __name__=='__main__':
    unittest.main()
