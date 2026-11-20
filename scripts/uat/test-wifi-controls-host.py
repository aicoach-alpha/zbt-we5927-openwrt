"""Exercise native UCI and libubox with fixture netifd, nl80211 and sysfs."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

pkg = Path(__file__).resolve().parents[2] / 'rebuild/veci-v2/packages/veci-v2-runtime'
uci = Path(sys.argv[1]).resolve(strict=True)
prefix = Path(sys.argv[2]).resolve(strict=True)
with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    config = root / 'config'
    config.mkdir()
    (root / 'delta').mkdir()
    wireless = config / 'wireless'
    wireless.write_text("config wifi-device 'radio0'\n option band '2g'\n option channel '1'\n"
                        "config wifi-iface 'default_radio0'\n option device 'radio0'\n option mode 'ap'\n"
                        " option encryption 'psk2'\n option key 'initial123'\n"
                        "config wifi-iface 'guest'\n option ssid 'Guest'\n")
    (root / 'board').write_text('zbtlink,zbt-we5927\n')
    phy = root / 'sys/wlan0/phy80211/name'
    phy.parent.mkdir(parents=True)
    phy.write_text('phy0\n')
    helper = root / 'controls'
    helper.write_text((pkg / 'veci2-wifi-controls').read_text()
                      .replace('/sys/class/net/', str(root / 'sys') + '/')
                      .replace('/usr/share/libubox/jshn.sh', str(prefix / 'share/libubox/jshn.sh')))
    provider = root / 'provider'
    provider.write_text((pkg / 'veci2-wifi').read_text().replace('/tmp/sysinfo/board_name', str(root / 'board'))
                        .replace('/usr/libexec/veci2-wifi-controls', str(helper)))
    scripts = {
        'uci': f'#!/bin/sh\nexec "{uci}" -c "{config}" -t "{root}/delta" "$@"\n',
        'ubus': '#!/bin/sh\necho radio\n',
        'jsonfilter': '#!/usr/bin/env python3\nimport json,sys\nprint("wlan0" if sys.argv[2]=="radio" else json.loads(sys.argv[2])[sys.argv[4][2:]])\n',
        'iw': """#!/bin/sh
case "$*" in
  'phy phy0 info') printf '%s\\n' '* 2412 MHz [1] (20.0 dBm)' '* 2437 MHz [6] (20.0 dBm)' '* 2462 MHz [11] (disabled)' ;;
  'dev wlan0 station dump') echo 'Station 02:12:34:56:78:9a (on wlan0)' ;;
  'dev wlan0 scan passive') printf '%s\\n' 'BSS 02:12:34:56:78:9a(on wlan0)' ' freq: 2437' ' signal: -54.00 dBm' ' SSID: nearby "one"' ;;
  *) exit 1 ;;
esac
""",
    }
    for name, body in scripts.items():
        path = root / name
        path.write_text(body)
        path.chmod(0o700)
    env = dict(os.environ, PATH=f'{root}:{prefix}/bin:' + os.environ['PATH'])
    def call(method, **args):
        result = subprocess.run(['busybox', 'ash', provider, 'call', method], input=json.dumps(args),
                                text=True, env=env, capture_output=True, timeout=8)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    def value(key):
        return subprocess.check_output([root / 'uci', 'get', 'wireless.' + key], env=env, text=True).strip()
    info = call('info')
    assert info['channels'] == [1, 6] and info['clients'] == ['02:12:34:56:78:9a'], info
    assert call('survey')['networks'][0]['ssid'] == 'nearby "one"'
    assert call('setChannel', channel='11')['error'] == 'channel_unavailable'
    assert call('setChannel', channel='6')['saved'] and value('radio0.channel') == '6'
    assert call('setAccess', mode='allow', addresses='')['error'] == 'empty_allow_list'
    for bad in ('01:00:00:00:00:01','00:00:00:00:00:00','not-a-mac'):
        assert call('setAccess', mode='deny', addresses=bad)['error'] == 'invalid_access'
    mac = '02:ab:cd:ef:12:34'
    for mode in ('allow','deny'):
        assert call('setAccess', mode=mode, addresses=mac.upper() + ' ' + mac)['saved']
        data = call('info')
        assert data['access'] == mode and data['addresses'] == [mac], data
    assert call('setAccess', mode='disable', addresses='')['saved'] and call('info')['addresses'] == []
    assert call('setAuth', mode='none', key_hex='61'*8)['error'] == 'invalid_security'
    key = b'New key! $'
    assert call('setAuth', mode='sae-mixed', key_hex=key.hex())['saved']
    assert value('default_radio0.key') == key.decode() and key.decode() not in str(call('info'))
    assert value('guest.ssid') == 'Guest'
    subprocess.run([root/'uci','set','wireless.guest.ssid=Pending'], env=env, check=True)
    assert call('setAccess', mode='disable', addresses='')['error'] == 'pending_wireless_changes'
    print('PASS: native UCI/jshn, ACL modes, invalid MACs/empty allow list, deduplication, associated clients, legal channels, passive scan, auth, pending edits, guest preservation')
