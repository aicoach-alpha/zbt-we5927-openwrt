import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LTE = ROOT / 'source/we5927-lte/files/usr/sbin/we5927-lte'
LOGGER = ROOT / 'source/we5927-lte/files/usr/sbin/veci-reliability'

def function(name):
    src = LTE.read_text()
    begin = src.index(name+'() {')
    end = src.index('\n}\n',begin)+2
    return src[begin:end]

MOCK = r'''
log() { printf "LOG:%s\n" "$*" >> "$CALLS"; }
cfg() {
 case "$1" in
   sim) echo 1;;fail_threshold) echo 2;;ping_interval) echo 5;;
   hard_reset_after) echo 2;;auto_failover) echo 0;;
 esac
}
clamped_number() { echo "$1"; }
enabled() { return 0; }
ensure_network() { :; }
power_on() { :; }
set_sim() { :; }
usb_repair() { :; }
wait_at() { :; }
sim_ready() { :; }
apply_apn() { :; }
ifup() { :; }
data_ok() { return 1; }
gateway_ok() { [ "$MOCK_GW" = 1 ]; }
https_ok() { [ "$MOCK_HTTPS" = 1 ]; }
wan_diag_event() { printf "EVENT:%s:%s\n" "$1" "$2" >> "$CALLS"; }
renew_lte() { echo RENEW >> "$CALLS"; return 1; }
repair_lte_interface() { echo IFDOWN_IFUP >> "$CALLS"; return 1; }
soft_reconnect() { echo CFUN >> "$CALLS"; return 1; }
power_cycle() { echo POWER_CYCLE >> "$CALLS"; }
auto_switch_sim() { echo SIM_FAILOVER >> "$CALLS"; }
radio_or_link_lost() { return 1; }
performance_state() { printf "STAGE:%s\n" "$stage" >> "$CALLS"; }
sleep() {
    loops=$((loops+1))
    [ "$loops" -ge 2 ] && exit 0
    return 0
}
'''
DAEMON = function('daemon')

class GatewayFirst(unittest.TestCase):
    def case(self,gw,https):
        with tempfile.TemporaryDirectory() as td:
            trace=Path(td)/'trace'
            env={**os.environ,'CALLS':str(trace),'MOCK_GW':str(gw),
                 'MOCK_HTTPS':str(https)}
            code=MOCK+'\n'+DAEMON+'\nloops=0;daemon\n'
            out=subprocess.run(['busybox','ash','-c',code],env=env,
                        capture_output=True,text=True,timeout=8)
            self.assertEqual(out.returncode,0,out.stderr)
            return trace.read_text()

    def test_gateway_healthy_https_healthy_no_renew(self):
        text=self.case(1,1)
        self.assertIn('EVENT:icmp_failed_https_ok:hold_gateway_healthy',text)
        self.assertIn('STAGE:icmp_degraded_https_ok',text)
        self.assertNotIn('RENEW',text)
        self.assertNotIn('IFDOWN_IFUP',text)
        self.assertNotIn('CFUN',text)
        self.assertNotIn('POWER_CYCLE',text)

    def test_gateway_healthy_https_failed_still_no_renew(self):
        text=self.case(1,0)
        self.assertIn('EVENT:icmp_and_https_failed:hold_gateway_healthy',text)
        self.assertIn('STAGE:upstream_degraded',text)
        for action in ('RENEW','IFDOWN_IFUP','CFUN','POWER_CYCLE'):
            self.assertNotIn(action,text)

    def test_daemon_restart_preserves_healthy_modem_gpio(self):
        with tempfile.TemporaryDirectory() as td:
            trace=Path(td)/'trace'
            mock=MOCK+"""
power_on() { echo UNEXPECTED_MODEM_GPIO >> "$CALLS"; }
set_sim() { echo UNEXPECTED_SIM_GPIO >> "$CALLS"; }
data_ok() { return 0; }
sleep() { exit 0; }
"""
            out=subprocess.run(['busybox','ash','-c',mock+'\n'+DAEMON+'\ndaemon\n'],
                  env={**os.environ,'CALLS':str(trace),
                       'MOCK_GW':'1','MOCK_HTTPS':'1'},
                  capture_output=True,text=True,timeout=6)
            self.assertEqual(out.returncode,0,out.stderr)
            content=trace.read_text()
            self.assertNotIn('UNEXPECTED_',content)
            self.assertIn('STAGE:healthy',content)

    def test_daemon_restart_gateway_healthy_public_icmp_down_no_gpio(self):
        with tempfile.TemporaryDirectory() as td:
            trace=Path(td)/'trace'
            mock=MOCK+"""
power_on() { echo UNEXPECTED_MODEM_GPIO >> "$CALLS"; }
set_sim() { echo UNEXPECTED_SIM_GPIO >> "$CALLS"; }
data_ok() { return 1; }
sleep() { exit 0; }
"""
            out=subprocess.run(['busybox','ash','-c',mock+'\n'+DAEMON+'\ndaemon\n'],
                  env={**os.environ,'CALLS':str(trace),'MOCK_GW':'1','MOCK_HTTPS':'0'},
                  capture_output=True,text=True,timeout=6)
            self.assertEqual(out.returncode,0,out.stderr)
            content=trace.read_text()
            self.assertNotIn('UNEXPECTED_',content)
            self.assertIn('preserving GPIOs and DHCP',content)

    def test_gateway_missing_allows_bounded_recovery(self):
        text=self.case(0,0)
        self.assertIn('RENEW',text)
        self.assertIn('IFDOWN_IFUP',text)
        self.assertNotIn('POWER_CYCLE',text)
        self.assertNotIn('SIM_FAILOVER',text)

    def test_reliability_report_classifies_healthy_https_and_failure(self):
        import time
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            directory=base/'persistent'
            directory.mkdir()
            local=base/'logger'
            local.write_text(LOGGER.read_text().replace(
               'DIR=/overlay/veci-reliability','DIR='+str(directory)))
            now=int(time.time())-150
            header=LOGGER.read_text().split("HEADER='",1)[1].split("'",1)[0]
            (directory/'samples-20261109.csv').write_text(header+'\n'+
               f'{now},1,1000,5,3,5,5,40,55,0,0,0,0,1,-44,72,healthy,ready,15000,0.2,5\n')
            (directory/'wan-health-20261109.csv').write_text(
               'epoch,classification,action\n'+
               f'{now},icmp_failed_https_ok,hold_gateway_healthy\n'+
               f'{now+2},icmp_and_https_failed,hold_gateway_healthy\n'+
               f'{now+4},local_gateway_failure,dhcp_renew_recovered\n')
            r=subprocess.run(['busybox','ash',str(local),'report','24'],
                  capture_output=True,text=True,timeout=6)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertIn('WAN_DIAG_EVENTS=3',r.stdout)
            self.assertIn('WAN_ICMP_FAILED_HTTPS_OK=1',r.stdout)
            self.assertIn('WAN_ICMP_AND_HTTPS_FAILED=1',r.stdout)
            self.assertIn('WAN_DHCP_RENEW_RECOVERED=1',r.stdout)
            self.assertIn('WIFI_ASSOCIATED_RSSI_AVG_DBM=-44.0',r.stdout)

    def test_audit_retention_rssi_and_small_https(self):
        src=LTE.read_text()
        self.assertIn("uclient-fetch -4 -q -T 5",src)
        self.assertIn('wan-health-',src)
        self.assertIn(' [ "$free" -ge 300 ] || return 0',src)
        self.assertIn('no DHCP renew or radio reset',src)
        logger=LOGGER.read_text()
        self.assertIn('if($14>0 && $15<=-10 && $15>=-120)',logger)
        self.assertIn("wan-health-*.csv",logger)
        for f in (LTE,LOGGER):
            r=subprocess.run(['sh','-n',str(f)],text=True,capture_output=True)
            self.assertEqual(r.returncode,0,r.stderr)

if __name__=='__main__':
    unittest.main()
