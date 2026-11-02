"""Non-live tests: updater must not occupy resident RAM when disabled."""
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
INIT=ROOT/'source/veci-update-we5927/files/etc/init.d/veci-update-agent'
AGENT=ROOT/'source/veci-update-we5927/files/usr/sbin/veci-update-agent'
DEFAULTS=ROOT/'source/veci-update-we5927/files/etc/uci-defaults/96-veci-update-we5927'
PACKAGE=ROOT/'source/veci-update-we5927/Makefile'


class UpdateAgentIdleTests(unittest.TestCase):
    def run_init(self, automatic):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d)
            bin=root/'bin'
            bin.mkdir()
            stub=bin/'uci'
            stub.write_text("#!/bin/sh\n"
                "if [ \"$1 $2 $3\" = \"-q get veci.update.auto_check\" ]; then\n"
                "  printf '%s\\n' \"$AUTO_CHECK\"\n"
                "else\n"
                "  exit 1\n"
                "fi\n")
            stub.chmod(0o755)
            source=INIT.read_text()
            source+="\nprocd_open_instance() { echo open; }\n"
            source+="procd_set_param() { echo param:$*; }\n"
            source+="procd_close_instance() { echo close; }\n"
            source+="procd_add_reload_trigger() { echo trigger:$*; }\n"
            source+="start_service; service_triggers\n"
            env={**os.environ,'PATH':str(bin)+':'+os.environ.get('PATH',''),
                 'AUTO_CHECK':automatic}
            run=subprocess.run(['sh','-c',source],capture_output=True,text=True,env=env,timeout=5)
            return run,run.stdout.splitlines()

    def test_disabled_no_procd_instance(self):
        run,actions=self.run_init('0')
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertEqual(actions,['trigger:veci'])

    def test_missing_setting_no_procd_instance(self):
        run,actions=self.run_init('')
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertEqual(actions,['trigger:veci'])

    def test_enabled_keeps_scheduled_checker_and_reload(self):
        run,actions=self.run_init('1')
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertIn('open',actions)
        self.assertIn('param:command /usr/sbin/veci-update-agent',actions)
        self.assertIn('param:respawn 3600 5 5',actions)
        self.assertIn('close',actions)
        self.assertEqual(actions[-1],'trigger:veci')

    def test_new_install_defaults_off_existing_choice_respected(self):
        setup=DEFAULTS.read_text()
        self.assertIn("uci -q get veci.update.auto_check",setup)
        self.assertIn("uci set veci.update.auto_check='0'",setup)
        self.assertNotIn("uci set veci.update.auto_check='1'",setup)
        self.assertIn('PKG_RELEASE:=2',PACKAGE.read_text())

    def test_agent_exits_instead_of_idle_sleep_when_disabled(self):
        content=AGENT.read_text()
        self.assertIn('while [ "$(uci -q get veci.update.auto_check',content)
        self.assertNotIn('while true; do',content)
        self.assertIn('check_once',content)
        self.assertIn('veci.update.auto_install',content)
        self.assertIn('signature_verified',content)

    def test_shell_syntax(self):
        for path in (INIT,AGENT,DEFAULTS):
            with self.subTest(path=path.name):
                run=subprocess.run(['sh','-n',str(path)],capture_output=True,text=True)
                self.assertEqual(run.returncode,0,run.stderr)

    def test_no_live_router_mutation_in_tests(self):
        source=INIT.read_text()
        self.assertNotIn('sysupgrade',source)
        self.assertNotIn('apk del',source)
        self.assertIn('procd_add_reload_trigger veci',source)


if __name__=='__main__':
    unittest.main()
