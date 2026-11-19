"""Exercise native firewall RPC against disposable UCI config; no live firewall."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

uci, prefix = map(Path, sys.argv[1:])
runtime = Path(__file__).resolve().parents[2] / 'rebuild/veci-v2/packages/veci-v2-runtime'
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    delta = root/'delta'
    delta.mkdir()
    (root/'board').write_text('zbtlink,zbt-we5927\n')
    (root/'network').write_text("config interface 'lan'\n option ipaddr '192.168.44.1/26'\n")
    fw = root/'firewall'
    fw.write_text("config zone 'inside'\n option name lan\n list network lan\n option input ACCEPT\n"
                  "config zone\n option name wan\n list network wan\n option input REJECT\n"
                  "config rule 'keep'\n option name 'allow dns'\n")
    source = (runtime/'veci2-firewall').read_text()
    for key, value in {'/tmp/sysinfo/board_name':root/'board','/var/lock/veci2-ipv6.lock':root/'lock',
            '/etc/config/firewall':fw, '/etc/config/network':root/'network',
            '/usr/share/libubox/jshn.sh':prefix/'share/libubox/jshn.sh',
            '/usr/libexec/veci2-lan-bounds':runtime/'veci2-lan-bounds'}.items():
        source = source.replace(key, str(value))
    provider = root/'provider'
    provider.write_text(source)
    shim = root/'uci'
    shim.write_text(f'#!/bin/sh\nexec "{uci}" -c "{root}" -t "{delta}" "$@"\n')
    shim.chmod(0o700)
    env = dict(os.environ, PATH=f'{root}:{prefix}/bin:' + os.environ['PATH'], LD_LIBRARY_PATH=str(prefix/'lib'))
    def call(method, **params):
        result = subprocess.run(['busybox','ash',provider,'call',method], env=env,
            input=json.dumps(params), capture_output=True, check=True, text=True, timeout=5)
        return json.loads(result.stdout)
    def save(method, **params):
        return call(method, revision=call('status')['revision'], **params)
    state = call('status')
    assert len(state['zone']) == 2 and state['redirect'] == [], state
    zone = dict(section=state['zone'][1]['section'], input='DROP', output='ACCEPT', forward='REJECT', masq='1', confirm='SAVE_ZONE')
    assert save('setZone', **dict(zone,input='ANY'))['error'] == 'invalid_policy'
    assert save('setZone', **zone)['ok']
    assert call('status')['zone'][1]['input'] == 'DROP'
    assert call('setZone', revision=state['revision'], **zone)['error'] == 'stale_configuration'
    rule = dict(kind='port', ip='192.168.44.10', proto='tcp', ext='1443', port='443', confirm='SAVE_FORWARD')
    for address in ['192.168.44.1','192.168.44.63','192.168.44.64','224.0.0.1']:
        assert save('addRedirect', **dict(rule,ip=address))['error'] == 'invalid_lan_address'
    for port in ['0','001','65536','80:82']:
        assert save('addRedirect', **dict(rule,ext=port))['error'] == 'invalid_port'
    assert save('addRedirect', **rule)['ok']
    assert save('addRedirect', **rule)['error'] == 'port_in_use'
    redirect = call('status')['redirect'][0]
    assert (redirect['dest_ip'],redirect['src_dport'],redirect['dest_port']) == ('192.168.44.10','1443','443')
    dmz = dict(rule, kind='dmz', proto='all', ext='', port='')
    assert save('addRedirect', **dmz)['error'] == 'confirmation_required'
    assert save('addRedirect', **dict(dmz,confirm='SAVE_ALL_PORTS_TO_HOST'))['ok']
    assert save('addRedirect', **dict(rule,ext='80'))['error'] == 'catch_all_exists'
    assert save('deleteRedirect',section=redirect['section'],confirm='DELETE_REDIRECT')['ok']
    assert len(call('status')['redirect']) == 1
    assert "allow dns" in fw.read_text()
    with (root/'lock').open('a') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        assert call('status')['error'] == 'busy'
    subprocess.run([shim,'set','firewall.keep.name=pending'],env=env,check=True)
    assert call('status')['error'] == 'pending_changes'
    (root/'board').write_text('other\n')
    assert call('status')['error'] == 'wrong_board'
    acl = json.loads((runtime/'veci2-firewall-acl.json').read_text())['veci-v2-firewall']
    assert acl['read']['ubus']['veci.v2.firewall'] == ['status']
    assert sorted(acl['write']['ubus']['veci.v2.firewall']) == ['addRedirect','deleteRedirect','setZone']
    print('PASS native UCI firewall zones, masquerading, port DNAT, DMZ, conflicts, address bounds, lock, revision, ACL')
