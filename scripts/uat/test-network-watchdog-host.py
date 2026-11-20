"""Persist an existing modem monitor setting with native UCI and a simulated modem."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

runtime = Path(__file__).resolve().parents[2] / 'rebuild/veci-v2/packages/veci-v2-runtime'
binary = Path(sys.argv[1]).resolve(strict=True)
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    cfg = root / 'cfg'
    delta = root / 'delta'
    cfg.mkdir()
    delta.mkdir()
    config = cfg / 'we5927_lte'
    config.write_text("config modem 'main'\n option apn 'office'\n option fail_threshold '5'\n")
    board = root / 'board'
    board.write_text("zbtlink,zbt-we5927\n")
    provider = root / 'provider'
    provider.write_text((runtime/'veci2-lte-policy').read_text().replace(
        '/tmp/sysinfo/board_name', str(board)).replace('/usr/sbin/we5927-lte', str(root/'modem')))
    scripts = {'uci': f'#!/bin/sh\nexec "{binary}" -c "{cfg}" -t "{delta}" "$@"\n',
               'modem': '#!/bin/sh\ncase "$1" in selector-slot) echo 1;; sim-request-status) echo idle;; validate-apn) exit 0;; *) exit 2;; esac',
               'jsonfilter': '#!/usr/bin/env python3\nimport json,sys\nprint(json.loads(sys.argv[2])[sys.argv[4][2:]])'}
    for name, body in scripts.items():
        path = root/name
        path.write_text(body)
        path.chmod(0o700)
    env = dict(os.environ, PATH=f"{root}:" + os.environ['PATH'])
    def call(method, **params):
        return json.loads(subprocess.check_output(['busybox', 'ash', provider, 'call', method], env=env,
                          input=json.dumps(params), text=True, timeout=4))
    assert call('status')['monitor_interval'] == 10
    before = config.read_bytes()
    for value in ('4', '121', '-5', '00', '10000000000000'):
        assert call('setMonitor', expected='10', interval=value)['error'] == 'invalid_interval'
        assert config.read_bytes() == before
    for previous, interval in [('10','5'), ('5','120'), ('120','60')]:
        assert call('setMonitor', expected=previous, interval=interval)['monitor_interval'] == int(interval)
        assert call('status')['configured_apn'] == 'office'
        assert call('setMonitor', expected=previous, interval=interval)['error'] == 'stale_interval'
    with provider.open() as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        assert call('setMonitor', expected='60', interval='30')['error'] == 'busy'
    assert subprocess.check_output([root/'uci', 'get', 'we5927_lte.main.fail_threshold'], text=True).strip() == '5'
    subprocess.run([root/'uci','set','we5927_lte.main.apn=pending'], check=True)
    assert call('setMonitor', expected='60', interval='30')['error'] == 'pending_lte_changes'
    acl = json.loads((runtime/'veci2-status-acl.json').read_text())['veci-v2-lte']
    assert 'setMonitor' in acl['write']['ubus']['veci.v2.lte']
    assert 'setMonitor' not in acl['read']['ubus']['veci.v2.lte']
    print('PASS existing LTE monitor interval: defaults, endpoints, persistence, stale/invalid refusal, lock, pending configuration, unchanged APN/threshold and ACL')
