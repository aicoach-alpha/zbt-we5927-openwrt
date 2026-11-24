"""Run the SMS wrappers and native transports on a pseudoterminal without a modem."""
import json
import os
from pathlib import Path
import pty
import select
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SMS = ROOT / 'source/veci-cellular-we5927/files/usr/libexec'
NATIVE = ROOT / 'source/we5927-lte/src'
SUBMIT = '000100049121430000024120'


class SmsPortTransaction(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.master, slave = pty.openpty()
        self.addCleanup(os.close, self.master)
        self.addCleanup(os.close, slave)
        self.port = os.ttyname(slave)
        self.selected = self.root / 'selected'
        self.selected.write_text(self.port + '\n')
        (self.root / 'board').write_text('zbtlink,zbt-we5927\n')
        (self.root / 'config').touch()
        manager = self.root / 'manager'
        manager.write_text(f'#!/bin/sh\n[ "$1" = at-port ] && cat {self.selected}\n')
        manager.chmod(0o700)
        for helper in ('we5927-at', 'veci-sms-cmgs'):
            source = (NATIVE / (helper + '.c')).read_text()
            # Exercise production USB validation using our PTY as its serial device.
            source = source.replace('"/dev/ttyUSB"', '"/dev/pts/"').replace(
                '/usr/sbin/we5927-lte at-port', str(manager) + ' at-port')
            src = self.root / (helper + '.c')
            src.write_text(source)
            subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', str(src),
                            '-o', str(self.root / helper)], check=True)

    def transaction(self, action, steps, change_after=None):
        code = (SMS / ('veci-sms-' + action + '-one')).read_text()
        for old, new in {
            '/usr/sbin/we5927-at': 'we5927-at', '/usr/sbin/we5927-lte': 'manager',
            '/usr/libexec/veci-sms-cmgs': 'veci-sms-cmgs',
            '/tmp/sysinfo/board_name': 'board', '/etc/config/veci_sms': 'config',
            '/var/lock/we5927-at.lock': 'lock',
        }.items():
            code = code.replace(old, str(self.root / new))
        code = code.replace('set -eu', 'set -eu\nid() { echo 0; }\nuci() { echo 1; }')
        args = ['sh', '-c', code, action]
        if action == 'delete':
            args.extend(['3', 'SM'])
        with subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE) as process:
            try:
                process.stdin.write((SUBMIT if action == 'send' else '0001').encode())
                process.stdin.close()
                for sent, reply in steps:
                    data = b''
                    while len(data) < len(sent):
                        self.assertTrue(select.select([self.master], [], [], 3)[0], sent)
                        data += os.read(self.master, 256)
                    self.assertEqual(data, sent)
                    if sent == change_after:
                        self.selected.write_text('/dev/ttyUSB9\n')
                    os.write(self.master, reply)
                process.wait(timeout=3)
                self.assertFalse(select.select([self.master], [], [], 0)[0])
                return json.loads(process.stdout.read())
            finally:
                if process.poll() is None:
                    process.kill()

    def test_send_once_and_restore_sms_mode(self):
        result = self.transaction('send', [
            (b'AT+CMGF?\r', b'\r\n+CMGF: 1\r\nOK\r\n'),
            (b'AT+CMGF=0\r', b'OK\r\n'),
            (b'AT+CMGS=11\r', b'> '),
            (SUBMIT.encode() + b'\x1a', b'\r\n+CMGS: 7\r\nOK\r\n'),
            (b'AT+CMGF=1\r', b'OK\r\n'),
        ])
        self.assertEqual(result, {'ok': True, 'status': 'accepted_by_modem'})

    def deletion(self, changed):
        steps = [(b'AT+CPMS?\r', b'+CPMS: "SM",1,10\r\nOK\r\n'),
                 (b'AT+CMGF?\r', b'+CMGF: 0\r\nOK\r\n'),
                 (b'AT+CMGR=3\r', b'+CMGR: 0,,1\r\n0001\r\nOK\r\n')]
        if not changed:
            steps.append((b'AT+CMGD=3,0\r', b'OK\r\n'))
        return self.transaction('delete', steps, b'AT+CMGR=3\r' if changed else None)

    def test_delete_matching_message(self):
        self.assertEqual(self.deletion(False), {'ok': True, 'deleted': 3, 'storage': 'SM'})

    def test_port_change_before_delete(self):
        self.assertFalse(self.deletion(True)['ok'])

    def test_port_change_before_submit(self):
        result = self.transaction('send', [(b'AT+CMGF?\r', b'+CMGF: 0\r\nOK\r\n')],
                                  b'AT+CMGF?\r')
        self.assertFalse(result['ok'])
