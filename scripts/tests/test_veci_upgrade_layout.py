"""Offline gate tests. No flash commands or physical devices are used."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
VERIFY = ROOT / 'rebuild/veci-v2/packages/veci-v2-runtime/veci2-verify-image'
ANCHOR = ROOT / 'rebuild/veci-v2/trust/1d8759d36251c36c'
PARTITION = 'mtd3: 007a0000 00010000 "firmware"\n'


class UpgradeCompatibilityTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.image = self.root / 'candidate.bin'
        self.image.write_bytes(b'fixture')
        self.digest = hashlib.sha256(self.image.read_bytes()).hexdigest()
        self.mtd = self.root / 'mtd'
        self.mtd.write_text(PARTITION)
        board = self.root / 'board'
        board.write_text('zbtlink,zbt-we5927\n')
        self.meta = {'version': {'target': 'ramips/mt76x8'},
                     'supported_devices': ['zbt-we5927', 'zbtlink,zbt-we5927']}
        self.verify = self.root / 'verify'
        self.verify.write_text(VERIFY.read_text().replace('/proc/mtd', str(self.mtd))
                               .replace('/tmp/sysinfo/board_name', str(board))
                               .replace('/etc/opkg/keys/1d8759d36251c36c', str(ANCHOR)))
        self.marker = self.root / 'sysupgrade-test'
        for name, body in {
            'fwtool': '#!/bin/sh\nif [ "$2" = -i ]; then printf "%s" "$METADATA" > "$3"; fi\n',
            'ucert': '#!/bin/sh\ncat >/dev/null\n',
            'jsonfilter': """#!/usr/bin/env python3
import json, sys
m = json.load(open(sys.argv[2]))
if sys.argv[4] == '@.version.target':
    print(m['version']['target'])
elif sys.argv[4] == '@.supported_devices[*]':
    print(*m['supported_devices'], sep='\\n')
else:
    sys.exit(1)
""",
            'sysupgrade': '#!/bin/sh\n[ "$1" = -T ] && [ "$#" = 2 ] && echo test > "$MARKER"\n',
        }.items():
            command = self.root / name
            command.write_text(body)
            command.chmod(0o700)

    def verify_result(self, error=None):
        result = subprocess.run(['sh', str(self.verify), str(self.image), self.digest],
                                env=dict(os.environ, PATH=f'{self.root}:' + os.environ['PATH'],
                                         METADATA=json.dumps(self.meta), MARKER=str(self.marker)),
                                text=True, capture_output=True, timeout=5)
        if error:
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(error, result.stderr)
            self.assertFalse(self.marker.exists())
        else:
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(self.marker.is_file())

    def test_layout_uses_label_and_accepts_different_mtd_index(self):
        self.mtd.write_text(PARTITION.replace('mtd3', 'mtd12'))
        self.verify_result()

    def test_rejects_unconfirmed_or_different_partition(self):
        for layout in ('', PARTITION * 2, PARTITION.replace('7a', '7b'),
                       PARTITION.replace('7a', '79'), PARTITION.replace('00010000', '00020000'),
                       PARTITION.replace('firmware', 'rootfs'), PARTITION.replace('mtd3', 'fake')):
            with self.subTest(layout=layout):
                self.mtd.write_text(layout)
                self.verify_result('incompatible_flash_layout')
        self.mtd.unlink()
        self.verify_result('incompatible_flash_layout')

    def test_wrong_image_target(self):
        self.meta['version']['target'] = 'ramips/mt7621'
        self.verify_result('incompatible_target')

    def test_exact_supported_device_required(self):
        self.meta['supported_devices'] = ['zbtlink,zbt-we5927-other', 'zbt-we5927']
        self.verify_result('incompatible_device')
