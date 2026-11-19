"""Exercise LAN reservations, DHCP pool and upstream DNS on disposable native UCI."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

runtime = Path(__file__).resolve().parents[2] / 'rebuild/veci-v2/packages/veci-v2-runtime'
uci, prefix = map(Path, sys.argv[1:])
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    config, delta = root / 'config', root / 'delta'
    config.mkdir()
    delta.mkdir()
    board = root / 'board'
    board.write_text('zbtlink,zbt-we5927\n')
    (config/'network').write_text("config interface 'lan'\n option ipaddr '192.168.44.1/26'\n")
    dhcp = config/'dhcp'
    dhcp.write_text("config dnsmasq\n list server '/corp/10.0.0.1'\nconfig dhcp 'lan'\n option interface 'lan'\n option start '10'\n option limit '10'\n option leasetime '12h'\nconfig host\n option mac '02:00:00:00:00:01'\n option ip '192.168.44.4'\n option name 'old'\n")
    marker = root/'reload'
    scripts = {
        'uci': f'exec "{uci}" -c "{config}" -t "{delta}" "$@"',
        'dnsmasq': f'test "$1" = reload && touch "{marker}"',
    }
    for name, body in scripts.items():
        executable = root / name
        executable.write_text('#!/bin/sh\n' + body + '\n')
        executable.chmod(0o700)
    provider = root / 'provider'
    provider.write_text((runtime/'veci2-dhcp').read_text().replace('/tmp/sysinfo/board_name', str(board))
                        .replace('/var/lock/veci2-ipv6.lock', str(root/'shared.lock'))
                        .replace('/etc/config/dhcp', str(dhcp)).replace('/etc/init.d/dnsmasq', str(root/'dnsmasq'))
                        .replace('/usr/share/libubox/jshn.sh', str(prefix/'share/libubox/jshn.sh')))
    env = dict(os.environ, PATH=f'{root}:{prefix}/bin:' + os.environ['PATH'])
    def call(method, **args):
        return json.loads(subprocess.check_output(['busybox','ash',provider,'call',method],
                          env=env, input=json.dumps(args), text=True, timeout=5))
    def save(method, **args):
        return call(method, revision=call('status')['revision'], **args)
    with (root/'shared.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        assert call('status')['error'] == 'busy'
    state = call('status')
    assert state['ok'] and state['leases'][0]['section'] == '@host[0]', state
    for start, limit, reason in [('1','2','pool_contains_router'),('30','34','invalid_pool')]:
        assert save('savePool', start=start, limit=limit, time='12h')['error'] == reason
    assert save('savePool', start='30', limit='30', time='3h')['ok']
    assert call('savePool', revision=state['revision'], start='30', limit='30', time='2h')['error'] == 'stale_configuration'
    args = dict(section='', ip='192.168.44.5', name='office', mac='02:00:00:00:00:05')
    for ip in ['192.168.44.63','192.168.45.4','192.168.44.1','192.168.44.0']:
        assert save('saveLease', **dict(args,ip=ip))['error'] == 'invalid_ip'
    assert save('saveLease', **dict(args,ip='192.168.44.4'))['error'] == 'duplicate_ip'
    assert save('saveLease', **args)['ok']
    leases = call('status')['leases']
    assert len(leases) == 2 and leases[1]['name'] == 'office', leases
    assert save('saveLease', **dict(args,section=leases[1]['section'],name='office2'))['ok']
    assert save('deleteLease', section='lan')['error'] == 'unknown_lease'
    assert save('deleteLease', section=leases[1]['section'])['ok']
    assert call('status')['leases'] == state['leases']
    for op, expected in [('add',['/corp/10.0.0.1','9.9.9.9']),('remove',['/corp/10.0.0.1'])]:
        assert save('changeDns', op=op, server='9.9.9.9')['ok']
        assert call('status')['servers'] == expected
    assert save('apply', confirm='')['error'] == 'confirmation_required' and not marker.exists()
    assert save('apply', confirm='APPLY_DNSMASQ')['ok'] and marker.is_file()
    subprocess.run([root/'uci','set','dhcp.lan.start=20'], env=env, check=True)
    assert call('status')['error'] == 'pending_changes'
    board.write_text('unrelated\n')
    assert call('status')['error'] == 'wrong_board'
    print('PASS native UCI/BusyBox: pool geometry, router collision, leases CRUD, DNS preservation, stale and pending changes, explicit reload and board checks')
