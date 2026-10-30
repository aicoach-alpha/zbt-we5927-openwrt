import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'scripts/veci-flash-capacity-audit.sh'

class FlashCapacityAuditTests(unittest.TestCase):
    def execute(self, contents, board='zbtlink,zbt-we5927', target='ramips/mt76x8'):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d)
            mtd=root/'proc-mtd'
            mtd.write_text(contents)
            bin=root/'bin'
            bin.mkdir()
            ubus=bin/'ubus'
            ubus.write_text('#!/bin/sh\nprintf \'{"board_name":"test"}\\n\'\n')
            ubus.chmod(0o755)
            jsonfilter=bin/'jsonfilter'
            jsonfilter.write_text('#!/bin/sh\nfor arg; do case "$arg" in\n \'@.board_name\') echo "'+board+'";;\n \'@.release.target\') echo "'+target+'";;\nesac; done\n')
            jsonfilter.chmod(0o755)
            return subprocess.run(['sh',str(SCRIPT),str(mtd)],capture_output=True,text=True,
                    env={**os.environ,'PATH':str(bin)+':'+os.environ['PATH']},timeout=7)
    def test_shell_parses_and_no_system_mutation(self):
        r=subprocess.run(['sh','-n',str(SCRIPT)],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        s=SCRIPT.read_text()
        for forbidden in ('sysupgrade -','apk add ','uci set ','uci commit ',
                          '/etc/init.d/','mtd write','flashcp ','dd if=','reboot '):
            self.assertNotIn(forbidden,s)
    def test_exact_7808_kib_firmware_partition(self):
        r=self.execute('dev:    size   erasesize  name\nmtd0: 00040000 00010000 "u-boot"\nmtd3: 007a0000 00010000 "firmware"\n')
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertIn('MTD_FIRMWARE_BYTES=7995392',r.stdout)
        self.assertIn('MTD_GATE=PROFILE_LIMIT_FITS_REPORTED_PARTITION',r.stdout)
        self.assertIn('FLASH_DECISION=NO_GO_UNTIL_',r.stdout)
    def test_partitions_below_profile_budget_fail(self):
        r=self.execute('dev:    size   erasesize  name\nmtd3: 00790000 00010000 "firmware"\n')
        self.assertEqual(r.returncode,5,r.stdout+r.stderr)
        self.assertIn('PROFILE_LIMIT_EXCEEDS_REAL_FLASH_PARTITION',r.stdout)
        self.assertIn('FLASH_DECISION=NO_GO',r.stdout)
    def test_unknown_firmware_partition_fails(self):
        r=self.execute('dev:    size erasesize name\nmtd3: 007a0000 00010000 "rootfs"\n')
        self.assertEqual(r.returncode,4,r.stdout+r.stderr)
        self.assertIn('BLOCKED_MISSING',r.stdout)
    def test_ambiguous_firmware_partition_fails(self):
        r=self.execute('mtd3: 007a0000 00010000 "firmware"\nmtd5: 007b0000 00010000 "firmware"\n')
        self.assertEqual(r.returncode,4,r.stdout+r.stderr)
    def test_invalid_partition_hex_fails(self):
        for s in ('gggggggg','00000000','1111111111'):
            with self.subTest(s=s):
                r=self.execute('mtd3: '+s+' 00010000 "firmware"\n')
                self.assertNotEqual(r.returncode,0,r.stdout+r.stderr)
    def test_wrong_board_fails_before_capacity_claim(self):
        r=self.execute('mtd3: 007a0000 00010000 "firmware"\n',board='other,board')
        self.assertEqual(r.returncode,3,r.stdout+r.stderr)
        self.assertNotIn('MTD_FIRMWARE_BYTES',r.stdout)
    def test_wrong_openwrt_target_fails(self):
        r=self.execute('mtd3: 007a0000 00010000 "firmware"\n',target='ramips/mt7621')
        self.assertEqual(r.returncode,3,r.stdout+r.stderr)
    def test_windows_launcher_pins_script_sha_and_collects_blocked_report(self):
        ps=ROOT/'scripts/veci-flash-capacity-audit.ps1'
        content=ps.read_text()
        import hashlib
        expected=hashlib.sha256(SCRIPT.read_bytes()).hexdigest()
        self.assertIn(expected,content)
        self.assertIn('board_name',content)
        self.assertIn('ramips/mt76x8',content)
        self.assertIn('$auditExitCode = $LASTEXITCODE',content)
        self.assertIn('$report = ($auditOutput | Out-String).Trim()',content)
        self.assertIn('-flash-capacity.txt',content)
        self.assertIn('MTD_GATE=PROFILE_LIMIT_FITS_REPORTED_PARTITION',content)
        for forbidden in ('sysupgrade -F','apk add ','uci set ','uhttpd restart'):
            self.assertNotIn(forbidden,content)
        self.assertIn('VeCI-audits',content)

    def test_does_not_print_serial_or_imei(self):
        s=SCRIPT.read_text()
        for text in ('serial_number','imei','iccid','imsi','ifconfig','network.lan','wireless.@wifi-iface'):
            self.assertNotIn(text,s)

if __name__=='__main__': unittest.main()
