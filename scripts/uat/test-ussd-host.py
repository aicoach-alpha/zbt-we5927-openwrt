"""Exercise the packaged USSD RPC, native AT helper and delayed modem URCs."""
import json
import os
from pathlib import Path
import pty
import select
import subprocess
import sys
import tempfile
import threading
import time

repo = Path(__file__).resolve().parents[2]
prefix = Path(sys.argv[1]).resolve(strict=True)
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    at = root / 'at'
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', '-o', at,
                    repo/'source/we5927-lte/src/we5927-at.c'], check=True)
    master, slave = pty.openpty()
    manager = root / 'lte'
    manager.write_text('#!/bin/sh\ncase "$1" in\nselector-slot) echo 2;;\nat-port) echo ' +
                       os.ttyname(slave) + ';; esac\n')
    manager.chmod(0o700)
    board = root/'board'
    board.write_text('zbtlink,zbt-we5927\n')
    code = (repo/'rebuild/veci-v2/packages/veci-v2-runtime/veci2-ussd').read_text()
    for src, dst in {'/tmp/sysinfo/board_name':board, '/usr/sbin/we5927-lte':manager,
                     '/usr/sbin/we5927-at':at, '/var/lock/we5927-at.lock':root/'lock',
                     '/var/run/veci2-ussd-slot-':root/'pending-', '/usr/share/libubox/jshn.sh':
                     prefix/'share/libubox/jshn.sh'}.items():
        code = code.replace(src,str(dst))
    code = code.replace('--ussd-stdin 14000','--ussd-stdin 750')
    filt = root/'jsonfilter'
    filt.write_text('#!/usr/bin/env python3\nimport json,sys\nprint(json.load(sys.stdin)[sys.argv[-1][2:]])\n')
    filt.chmod(0o700)
    env = dict(os.environ, PATH=f'{root}:{prefix}/bin:' + os.environ['PATH'], LD_LIBRARY_PATH=str(prefix/'lib'))
    mode = ['delayed']
    sent = []
    stop = threading.Event()
    def modem():
        buf = b''
        while not stop.is_set():
            if not select.select([master],[],[],.05)[0]:
                continue
            buf += os.read(master,512)
            while b'\r' in buf:
                raw, buf = buf.split(b'\r',1)
                if raw == b'AT+CUSD=?':
                    os.write(master,b'\r\n+CUSD: (0-2)\r\nOK\r\n' if mode[0]!='unsupported' else b'\r\nERROR\r\n')
                elif raw == b'AT+CUSD=2':
                    os.write(master,b'\r\nOK\r\n')
                else:
                    sent.append(raw)
                    os.write(master,b'\r\n' + raw + b'\r\nOK\r\n')
                    if mode[0]!='timeout':
                        time.sleep(.07)
                        os.write(master,b'\r\n+CUSD: 0,"Reply",15\r\n')
    worker = threading.Thread(target=modem)
    worker.start()
    try:
        def call(method, **args):
            p = subprocess.run(['busybox','ash','-c',code,'provider','call',method],
                               input=json.dumps(args), text=True, capture_output=True, env=env,
                               check=True, timeout=4)
            return json.loads(p.stdout)
        args = dict(slot='2', confirm='SEND_USSD_ONCE', code='*123#')
        assert call('status') == dict(ok=True,slot=2,available=True,pending=False)
        for key,val in [('confirm',''),('slot','1'),('code','*1";AT#')]:
            assert not call('send', **dict(args, **{key:val}))['ok']
        assert not sent
        reply = call('send', **args)
        assert reply == dict(ok=True,status=0,response='+CUSD: 0,"Reply",15'), reply
        mode[0] = 'timeout'
        assert call('send', **args)['error'] == 'response_unconfirmed'
        assert call('status')['pending']
        assert call('send', **args)['error'] == 'previous_request_pending'
        assert call('cancel', slot='2',confirm='CANCEL_USSD')['cancelled']
        assert not call('status')['pending']
        mode[0] = 'unsupported'
        assert call('send', **args)['error'] == 'unsupported_modem'
        assert sent == [b'AT+CUSD=1,"*123#",15'] * 2
        print('PASS PTY: confirmed one-shot, delayed carrier URC, timeout and explicit cancellation, wrong slot, invalid code and unsupported modem')
    finally:
        stop.set()
        worker.join()
        os.close(master)
        os.close(slave)
