"""Behavioral simulated reliability tests; NEVER touch a physical router."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import json
import time

ROOT=Path(__file__).resolve().parents[1]
MODEM=ROOT/'source/we5927-lte/files/usr/sbin/we5927-lte'
GUARD=ROOT/'source/we5927-lte/files/usr/sbin/veci-wifi-guardian'
CFG=ROOT/'source/we5927-lte/files/etc/config/we5927_lte'
GUARDCFG=ROOT/'source/we5927-lte/files/etc/config/veci_performance'

def fn(source,name):
    text=source.read_text()
    start=text.index(name+'() {')
    end=text.index('\n}\n',start)+2
    return text[start:end]

class PerformanceTest(unittest.TestCase):
    def test_bounded_multi_target_and_gateway_classification(self):
        source='\n'.join([fn(MODEM,x) for x in ('data_ok','gateway_ok')])
        mock=r"""
cfg() { case "$1" in data_if) echo usb0;; ping_host) echo 1.1.1.1;; esac; }
ip() {
 case "$1" in
  link) [ "$MOCK_LINK" = 1 ];;
  -4) if [ "$2" = addr ]; then
          [ "$MOCK_IP" = 1 ] && echo 'inet 192.168.7.104/24' || :;
       else echo 'default via 192.168.7.1 dev usb0'; fi;;
 esac
}
ping() {
 eval "target=\${$#}"
 case "$target" in
  1.1.1.1) [ "$MOCK_PRIMARY" = 1 ];;
  8.8.8.8) [ "$MOCK_SECONDARY" = 1 ];;
  192.168.7.1) [ "$MOCK_GATEWAY" = 1 ];;
  *) exit 61;;
 esac
}
"""
        for pri,sec,gw,expected in [
            ('1','0','1','online'),('0','1','1','online'),
            ('0','0','1','upstream'),('0','0','0','gateway_failed')]:
            with self.subTest(pri=pri,sec=sec,gw=gw):
                script=mock+source+"""
if data_ok; then echo online
elif gateway_ok; then echo upstream
else echo gateway_failed; fi
"""
                env={**os.environ,'MOCK_LINK':'1','MOCK_IP':'1',
                     'MOCK_PRIMARY':pri,'MOCK_SECONDARY':sec,'MOCK_GATEWAY':gw}
                result=subprocess.run(['busybox','ash','-c',script],env=env,text=True,capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(result.stdout.strip(),expected)
        self.assertIn('ping -I "$dev" -c 1 -W 1',source)

    def test_fast_path_never_uses_modem_reset_or_ifdown(self):
        source='\n'.join([fn(MODEM,x) for x in ('renew_lte',)])
        mock=r"""
log() { echo "log:$*" >&2; }
ubus() { echo 'netifd:renew' >> "$MOCK_CALL_LOG"; return 0; }
ifup() { echo 'netifd:ifup'; return 0; }
ifdown() { echo 'UNEXPECTED_IFDOWN' >> "$MOCK_CALL_LOG"; return 0; }
soft_reconnect() { echo 'UNEXPECTED_MODEM_CFUN' >> "$MOCK_CALL_LOG"; return 0; }
power_cycle() { echo 'UNEXPECTED_POWER_CYCLE' >> "$MOCK_CALL_LOG"; return 0; }
sleep() { :; }
data_ok() { return 0; }
"""
        with tempfile.TemporaryDirectory() as tmp:
            calllog=Path(tmp)/'calls.txt'
            p=subprocess.run(['busybox','ash','-c',mock+source+'\nrenew_lte\n'],
                             env={**os.environ, 'MOCK_CALL_LOG':str(calllog)},
                             capture_output=True,text=True,timeout=3)
            self.assertEqual(p.returncode,0,p.stderr)
            calls=calllog.read_text()
            self.assertIn('netifd:renew',calls)
            self.assertNotIn('UNEXPECTED_',calls)
        self.assertIn("network.interface.lte renew",source)

    def test_unsafe_usb_port_and_false_hard_reset_are_blocked(self):
        text=MODEM.read_text()
        self.assertNotIn('for p in "$preferred" /dev/ttyUSB2 /dev/ttyUSB1',text)
        self.assertIn('[ "$p" = /dev/ttyUSB2 ] || continue',text)
        self.assertIn('radio_or_link_lost()',text)
        self.assertIn("at 'AT+CGATT?' 1500",text)
        self.assertIn('! gateway_ok && radio_or_link_lost',text)

    def test_status_api_rejects_stale_tmpfs_health(self):
        rpc=ROOT/'source/veci-cellular-we5927/files/usr/libexec/rpcd/veci.cellular'
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            lte=root/'lte.state'
            wifi=root/'wifi.state'
            script=rpc.read_text()
            script=script.replace('/tmp/veci-lte-performance.state',str(lte))
            script=script.replace('/tmp/veci-wifi-performance.state',str(wifi))
            local=root/'veci.cellular'
            local.write_text(script)
            local.chmod(0o700)
            uci=root/'uci'
            uci.write_text('#!/bin/sh\ncase "$*" in *we5927_lte.main.ping_interval*) echo 10;; *veci_performance.wifi.interval*) echo 30;; esac\n')
            uci.chmod(0o700)
            env={**os.environ,'PATH':td+':'+os.environ['PATH']}
            def current():
                result=subprocess.run(['busybox','ash',str(local),'call','performanceStatus'],
                                      env=env,capture_output=True,text=True,timeout=5)
                self.assertEqual(result.returncode,0,result.stderr)
                return json.loads(result.stdout)
            now=int(time.time())
            lte.write_text('failures=0 recoveries=0 stage=healthy timestamp='+str(now)+'\n')
            wifi.write_text('wifi=ready failures=0 auto_recover=1 timestamp='+str(now)+'\n')
            good=current()
            self.assertEqual(good['lte']['stage'],'healthy')
            self.assertEqual(good['wifi']['stage'],'ready')
            self.assertTrue(good['wifi']['auto_recover'])
            lte.write_text('failures=0 recoveries=0 stage=healthy timestamp='+str(now-300)+'\n')
            wifi.write_text('wifi=ready failures=0 auto_recover=1 timestamp='+str(now-300)+'\n')
            old=current()
            self.assertEqual(old['lte']['stage'],'stale')
            self.assertEqual(old['wifi']['stage'],'stale')
            self.assertEqual(old['lte']['check_interval_seconds'],10)

    def test_wifi_guardian_check_is_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            def create(name,text):
                f=base/name;f.write_text('#!/bin/sh\n'+text);f.chmod(0o755)
            create('uci',"""
case "$*" in
 *wireless.radio0.disabled*) echo 0;;
 *wireless.default_radio0.mode*) echo ap;;
 *wireless.default_radio0.disabled*) echo 0;;
esac
""")
            create('ubus','echo "{\\"radio0\\":{\\"up\\":true}}"')
            create('jsonfilter','echo "$MOCK_UP"')
            create('iw','[ "$MOCK_AP" = 1 ] && printf "Interface wlan0\\n type AP\\n"')
            env={**os.environ, 'PATH':str(base)+':'+os.environ['PATH'], 'MOCK_UP':'true','MOCK_AP':'1'}
            ready=subprocess.run(['sh',str(GUARD),'check'],env=env,text=True,capture_output=True,timeout=3)
            self.assertEqual(ready.returncode,0,ready.stderr)
            self.assertIn('wifi=ready',ready.stdout)
            env['MOCK_UP']='false'
            down=subprocess.run(['sh',str(GUARD),'check'],env=env,text=True,capture_output=True,timeout=3)
            self.assertNotEqual(down.returncode,0)
            self.assertIn('wifi=ap_not_ready',down.stdout)
            # Only the daemon does potentially disruptive guarded recovery.
            self.assertNotIn('wifi up',fn(GUARD,'check_once'))

    def test_static_wifi_and_lte_safety_guards(self):
        m=MODEM.read_text()
        w=GUARD.read_text()
        c=CFG.read_text()
        self.assertIn("option ping_interval '10'",c)
        self.assertIn("option fail_threshold '3'",c)
        self.assertIn("option hard_reset_after '3'",c)
        for required in (
            'if gateway_ok; then','last_hard','[ "$gap" -ge 900 ]',
            'renew_lte || repair_lte_interface || soft_reconnect',
            'flock -n -x 9','/var/lock/we5927-at.lock',
            'if [ "$(cfg sim)" != "$slot" ]','gpio_set "$n" "$v"',
            'set_sim "$sim" >/dev/null 2>&1 || true',
        ):
            self.assertIn(required,m,required)
        self.assertIn('if [ "$n" = 0 ]; then',w)
        self.assertIn('wifi up radio0',w)
        self.assertIn('station_count',w)
        self.assertIn('last_repair',w)
        self.assertIn('[ "$gap" -ge 900 ]',w)
        for bad in ('uci set wireless.','uci commit wireless','iw dev wlan0 scan','wifi down','reboot'):
            self.assertNotIn(bad,w,bad)
        self.assertIn("option auto_recover '1'",GUARDCFG.read_text())
        for path in (MODEM,GUARD,ROOT/'source/we5927-lte/files/etc/init.d/veci-wifi-guardian'):
            result=subprocess.run(['sh','-n',str(path)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__': unittest.main()
