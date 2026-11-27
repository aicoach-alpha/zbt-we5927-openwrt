"""Run the owner rpcd providers on BusyBox and real libuci with a disposable LAN."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

runtime = Path(__file__).resolve().parents[2] / 'rebuild/veci-v2/packages/veci-v2-runtime'
uci, prefix = map(Path, sys.argv[1:])
with TemporaryDirectory() as tmp:
    root = Path(tmp)
    config, delta = root/'config', root/'delta'
    config.mkdir()
    delta.mkdir()
    board = root/'board'
    board.write_text('zbtlink,zbt-we5927\n')
    dhcp = config/'dhcp'
    dhcp.write_text("config dnsmasq\nconfig dhcp 'lan'\n option interface 'lan'\n")
    (config/'network').write_text("config interface 'lan'\n option ipaddr '192.168.5.1/27'\n")
    lock = root/'shared.lock'
    network_lock = root/'network.lock'
    init = root/'dnsmasq'
    for name, code in {
        'uci': f'#!/bin/sh\nexec "{uci}" -c "{config}" -t "{delta}" "$@"',
        'jsonfilter': '#!/usr/bin/env python3\nimport json,sys\na=sys.argv; d=json.loads(a[a.index("-s")+1]); k=a[a.index("-e")+1][2:]\nif k not in d:sys.exit(1)\nprint(d[k])',
        'dnsmasq': f'#!/bin/sh\n[ "$1" = restart ] || exit 3\nif test -f "{root}/fail_once"; then rm "{root}/fail_once"; exit 1; fi\necho restart >>"{root}/restarts"',
        'pidof': '#!/bin/sh\ntest "$1" = dnsmasq',
    }.items():
        path = root/name
        path.write_text(code+'\n')
        path.chmod(0o700)
    for name in ('veci2-static-leases','veci2-dns'):
        code = (runtime/name).read_text()
        for original, target in {
            '/tmp/sysinfo/board_name':board, '/etc/config/dhcp':dhcp,
            '/var/lock/veci2-dhcp.lock':lock, '/var/lock/veci2-ipv6.lock':network_lock, '/etc/config/network':config/'network', '/etc/init.d/dnsmasq':init, 'pidof dnsmasq':str(root/'pidof')+' dnsmasq',
            '/usr/libexec/veci2-lan-bounds':runtime/'veci2-lan-bounds',
            '/usr/share/libubox/jshn.sh':prefix/'share/libubox/jshn.sh',
        }.items():
            code = code.replace(original, str(target))
        (root/name).write_text(code)
    env = dict(os.environ, LD_LIBRARY_PATH=str(prefix/'lib')+':'+os.environ.get('LD_LIBRARY_PATH',''), PATH=f'{root}:{prefix}/bin:'+os.environ['PATH'])
    def call(provider, method, **fields):
        result = subprocess.run(['busybox','ash',root/provider,'call',method], input=json.dumps(fields),
                                env=env, text=True, capture_output=True, timeout=6)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    def lease(method, **kw):
        return call('veci2-static-leases',method,**kw)
    def dns(method, **kw):
        return call('veci2-dns',method,**kw)
    args = dict(mac='02:12:34:AB:CD:EF',ip='192.168.5.2',name='office')
    first = lease('status')
    assert first['leases'] == [] and len(first['revision']) == 64
    before = dhcp.read_bytes()
    for bad in [dict(ip='192.168.5.1'),dict(ip='192.168.5.31'),dict(ip='192.168.5.32'),
                dict(mac='01:00:00:00:00:01'),dict(mac='00:00:00:00:00:00'),
                dict(mac='02:00:00:00:00:01\nxx'),dict(name='-bad')]:
        assert not lease('add',**(args|bad))['ok'], bad
        assert dhcp.read_bytes() == before
    with lock.open('a') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        assert lease('add',**args)['error'] == 'busy'
        assert dns('set',mode='AUTO')['error'] == 'busy'
    pool=dict(start="10",limit="15",lease="1h",enabled="1",confirmation="SAVE_DHCP_POOL",revision=first["revision"])
    with network_lock.open("a") as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        assert lease("add",**args)["error"]=="network_busy"
        assert lease("setPool",**pool)["error"]=="network_busy"
    subprocess.run([root/"uci","set","network.lan.ipaddr=192.168.6.1/27"],check=True)
    assert lease("add",**args)["error"]=="pending_network_changes"
    subprocess.run([root/"uci","revert","network"],check=True)
    for patch in (dict(start="1"),dict(limit="30"),dict(lease="1s"),dict(revision="stale")):
        assert not lease("setPool",**(pool|patch))["ok"]
        assert dhcp.read_bytes()==before
    (root/"fail_once").touch()
    assert lease("setPool",**pool)["error"]=="dhcp_apply_failed_rollback_attempted"
    assert dhcp.read_bytes()==before
    pool_saved=lease("setPool",**pool)
    assert pool_saved["ok"],pool_saved
    for key,value in (("start","10"),("limit","15"),("leasetime","1h"),("ignore","0")):
        assert subprocess.check_output([root/"uci","get","dhcp.lan."+key],text=True).strip()==value
    first=pool_saved
    print("PASS native DHCP pool lifecycle and cross-service network locking")
    current = lease('add',**args)
    assert current.get('ok'), current
    assert current['leases'][0]['mac'] == args['mac'].lower(), current
    assert lease('add',**(args|dict(ip='192.168.5.5')))['error'] == 'duplicate_static_lease'
    deletion = dict(index=0,confirmation='DELETE_LEASE_0')
    assert lease('delete',**deletion,revision=first['revision'])['error'] == 'stale_configuration'
    assert lease('delete',**(deletion|dict(confirmation='')),revision=current['revision'])['error'] == 'confirmation_required'
    saved = dhcp.read_bytes()
    (root/'fail_once').touch()
    assert lease('delete',**deletion,revision=current['revision'])['error'] == 'dhcp_apply_failed_rollback_attempted'
    assert dhcp.read_bytes() == saved
    assert lease('delete',**deletion,revision=current['revision'])['leases'] == []
    settings = dict(mode='CUSTOM',primary='1.1.1.1',secondary='9.9.9.9')
    assert dns('set',**settings) == dict(ok=True,**settings)
    saved = dhcp.read_bytes()
    (root/'fail_once').touch()
    assert dns('set',mode='AUTO')['error'] == 'apply_failed_restored'
    assert dhcp.read_bytes() == saved
    assert dns('set',mode='AUTO')['mode'] == 'AUTO'
    def change(*cmd):
        subprocess.run([root/'uci',*cmd], env=env, check=True)
    change('add_list','dhcp.@dnsmasq[0].server=/corp/10.0.0.1')
    assert lease('add',**args)['error'] == 'pending_dhcp_changes'
    assert dns('set',**settings)['error'] == 'pending_dhcp_changes'
    change('commit','dhcp')
    saved = dhcp.read_bytes()
    assert dns('set',**settings)['error'] == 'unsupported_dns_config'
    assert dhcp.read_bytes() == saved
    board.write_text('other\n')
    assert dns('set',**settings)['error'] == lease('add',**args)['error'] == 'unsupported_board'
    print('PASS native UCI/BusyBox owner DNS AUTO/CUSTOM, DHCP reservations, IPv4 subnet, shared locking, stale delete, preservation, negative cases and byte-exact rollback')
