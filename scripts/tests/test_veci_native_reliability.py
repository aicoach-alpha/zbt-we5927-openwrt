import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / 'rebuild/veci-v2/packages/veci-v2-runtime'


class Reliability(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.board = self.dir / 'board'
        self.board.write_text('zbtlink,zbt-we5927\n')
        self.state = self.dir / 'state'
        self.fault = self.dir / 'fault'
        self.helper = self.dir / 'reliability'
        self.helper.write_text((RUNTIME / 'veci2-reliability').read_text().replace(
            '/tmp/sysinfo/board_name', str(self.board)).replace('/tmp/veci-wifi-performance.state',
            str(self.state)).replace('/tmp/veci-wifi-first-fault.txt', str(self.fault)))
        self.helper.chmod(0o700)

    def test_first_fault_preserved_and_untrusted_data_excluded(self):
        self.state.write_text('wifi=ready failures=0 rx_pse_resets=5 timestamp=123 other=private\n')
        evidence = 'schema=veci_wifi_first_fault_v1\nreason=phy_missing\ncapture_uptime_s=49\nprivate\n'
        self.fault.write_text(evidence)
        output = subprocess.check_output([self.helper], text=True)
        self.assertEqual(set(output.splitlines()), {'guardian_phase=ready', 'guardian_failures=0',
            'guardian_rx_pse_resets=5', 'guardian_epoch_s=123', 'first_fault_reason=phy_missing',
            'first_fault_uptime_s=49'})
        self.assertEqual(self.fault.read_text(), evidence)
        self.state.write_text('wifi=private failures=10foo rx_pse_resets=1e5 timestamp=-1\n')
        self.fault.unlink()
        self.fault.symlink_to(self.state)
        self.assertTrue(all(line.endswith('=unknown') for line in subprocess.check_output(
            [self.helper], text=True).splitlines()))
        self.board.write_text('other')
        result = subprocess.run([self.helper], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(result.stdout)

    def test_snapshot_binds_all_active_probes_to_verified_rndis_interface(self):
        source = (ROOT / 'scripts/veci-link-readonly-snapshot.sh').read_text().replace(
            'PATH=/usr/sbin:', f'PATH={self.dir}:/usr/sbin:').replace(
            '/usr/sbin/we5927-lte', str(self.dir / 'lte')).replace('/usr/libexec/veci2-reliability', str(self.helper))
        calls = self.dir / 'calls'
        for name, body in {'lte': 'echo "$STATE"', 'ip': 'echo "ip $*" >> "$CALLS"; echo "default via 192.0.2.1"',
                           'ping': 'echo "ping $*" >> "$CALLS"; exit 0'}.items():
            file = self.dir / name
            file.write_text('#!/bin/sh\n' + body + '\n')
            file.chmod(0o700)
        def run(state):
            return subprocess.run(['sh'], input=source, env=dict(os.environ, STATE=state, CALLS=str(calls)),
                                  text=True, capture_output=True, timeout=5)
        active = run('carrier_up usb2')
        self.assertEqual(active.returncode, 0, active.stderr)
        self.assertIn('public_ping_ok=1', active.stdout)
        self.assertTrue(all('usb2' in line for line in calls.read_text().splitlines()))
        calls.unlink()
        missing = run('other_device')
        self.assertEqual(missing.returncode, 0, missing.stderr)
        self.assertIn('public_ping_ok=0', missing.stdout)
        self.assertFalse(calls.exists())
        self.assertNotEqual(run('carrier_up ../private').returncode, 0)
        self.assertFalse(calls.exists())
