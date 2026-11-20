"""Exercise the SSH/HTTPS configuration provider with native UCI and BusyBox ash."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

pkg = Path(__file__).resolve().parents[2] / 'rebuild/veci-v2/packages/veci-v2-runtime'
uci_binary = Path(sys.argv[1]).resolve(strict=True)
prefix = Path(sys.argv[2]).resolve(strict=True)
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    cfg = root / 'config'
    delta = root / 'delta'
    cfg.mkdir()
    delta.mkdir()
    board = root / 'board'
    board.write_text('zbtlink,zbt-we5927\n')
    ssh = cfg / 'dropbear'
    ssh.write_text("config dropbear\n option Port '2222'\n option Interface 'lan'\n option RootPasswordAuth 'off'\n")
    web = cfg / 'uhttpd'
    web.write_text(f"config uhttpd 'main'\n list listen_https '[::]:443'\n option cert '{root}/crt'\n option key '{root}/key'\n")
    provider = root / 'access'
    provider.write_text((pkg / 'veci2-access').read_text().replace('/tmp/sysinfo/board_name', str(board))
                        .replace('/etc/config/', str(cfg) + '/')
                        .replace('/usr/share/libubox/jshn.sh', str(prefix / 'share/libubox/jshn.sh')))
    wrapper = root / 'uci'
    wrapper.write_text(f'#!/bin/sh\nexec "{uci_binary}" -c "{cfg}" -t "{delta}" "$@"\n')
    wrapper.chmod(0o700)
    env = dict(os.environ, PATH=f"{root}:{prefix}/bin:" + os.environ['PATH'])
    def call(method, **args):
        return json.loads(subprocess.check_output(['busybox', 'ash', provider, 'call', method],
                          input=json.dumps(args), text=True, env=env, timeout=4))
    initial = call('status')
    assert initial['ok'] and initial['ssh_port'] == '2222' and initial['root_password'] == 'off'
    version = initial['revision']
    start_bytes = ssh.read_bytes(), web.read_bytes()
    for bad in ('', '30', '001', '90000', '-1', '1e2', ' 60', '60;exit'):
        assert call('setIdle', seconds=bad, revision=version)['error'] == 'invalid_timeout'
    assert call('requireHttps', revision=version)['error'] == 'missing_certificate'
    assert start_bytes == (ssh.read_bytes(), web.read_bytes())
    with provider.open() as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        assert call('setIdle', revision=version, seconds='60')['error'] == 'busy'
    subprocess.run([wrapper, 'set', 'uhttpd.main.home=/www'], check=True, env=env)
    assert call('setIdle', seconds='60', revision=version)['error'] == 'pending_changes'
    subprocess.run([wrapper, 'revert', 'uhttpd'], check=True, env=env)
    saved = call('setIdle', seconds='600', revision=version)
    assert saved['idle'] == '600' and saved['root_password'] == 'off' and saved['ssh_interface'] == 'lan'
    assert web.read_bytes() == start_bytes[1]
    assert call('requireHttps', revision=version)['error'] == 'stale_configuration'
    (root / 'crt').write_text('test certificate')
    (root / 'key').write_text('test key')
    before = ssh.read_bytes()
    secure = call('requireHttps', revision=saved['revision'])
    assert secure['redirect_https'] == '1' and ssh.read_bytes() == before
    assert 'test key' not in str(secure)
    assert call('setIdle', seconds='0', revision=secure['revision'])['idle'] == '0'
    with ssh.open('a') as stream:
        stream.write("config dropbear\n option Port '22'\n")
    assert call('status')['error'] == 'multiple_ssh_instances'
    board.write_text('another-board\n')
    assert call('status')['error'] == 'unsupported_board'
    acl = json.loads((pkg / 'veci2-access-acl.json').read_text())['veci-v2-access']
    assert acl['read']['ubus']['veci.v2.access'] == ['status']
    assert set(acl['write']['ubus']['veci.v2.access']) == {'setIdle', 'requireHttps'}
print('PASS SSH/HTTPS status, idle timeout, TLS redirect preconditions, stale revisions, locking, pending changes, unrelated config preservation, board and ACL')
