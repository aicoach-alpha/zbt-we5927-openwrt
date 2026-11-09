import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'source/we5927-lte/files'
TOOL = BASE / 'usr/sbin/veci-ipv4-only'
POLICY = BASE / 'etc/sysctl.d/99-veci-ipv4-only.conf'
FIRSTBOOT = BASE / 'etc/uci-defaults/97-veci-ipv4-only'
PACKAGE = ROOT / 'source/we5927-lte/Makefile'

class IPv4OnlyTest(unittest.TestCase):
    def test_source_contains_only_ipv6_changes(self):
        script=TOOL.read_text()
        for phrase in ('network.$section.ipv6=0','network.$section.disabled=1',
          'dhcp.$section.ra=disabled','dhcp.$section.dhcpv6=disabled',
          'dhcp.$section.ndp=disabled','network.globals.ula_prefix',
          'net.ipv6.conf.$key.disable_ipv6=1', '/etc/init.d/odhcpd stop',
          'is_ipv4_default_up'):
            self.assertIn(phrase,script)
        for forbidden in ('/etc/init.d/network restart','/etc/init.d/dnsmasq stop',
          '/etc/init.d/firewall restart','wifi reload','wifi down',
          'ifdown lte','ifup lte','reboot','AT+CFUN','rm -rf /overlay',
          'veci-reliability stop'):
            self.assertNotIn(forbidden,script)
        for key in ('default','all','lo'):
            self.assertIn('net.ipv6.conf.'+key+'.disable_ipv6=1',POLICY.read_text())
        self.assertIn('/usr/sbin/veci-ipv4-only apply-boot',FIRSTBOOT.read_text())
        self.assertRegex(PACKAGE.read_text(),r'PKG_RELEASE:=[67]')
        for filename in (TOOL,FIRSTBOOT):
            r=subprocess.run(['sh','-n',str(filename)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)

    def fixture(self,path,ipv4=True,main_dhcp4=False):
        path=Path(path)
        script=TOOL.read_text()
        sysctl_path=path/'ipv4-only.conf'
        sysctl_path.write_text(POLICY.read_text())
        odhcpd=path/'odhcpd'
        odhcpd.write_text('#!/bin/sh\nprintf "odhcpd %s\\n" "$1" >> "$TRACE"\n')
        odhcpd.chmod(0o755)
        script=script.replace('/etc/sysctl.d/99-veci-ipv4-only.conf',str(sysctl_path))
        script=script.replace('/etc/init.d/odhcpd',str(odhcpd))
        target=path/'veci-ipv4-only'
        target.write_text(script)
        target.chmod(0o755)
        def create(name,content):
            f=path/name;f.write_text('#!/bin/sh\n'+content+'\n');f.chmod(0o755)
        create('uci', '''
case "$1 $2" in
  '-q show') case "$3" in
    network) printf 'network.lan=interface\\nnetwork.lte=interface\\nnetwork.wan6=interface\\n' ;;
    dhcp) printf 'dhcp.lan=dhcp\\ndhcp.guest=dhcp\\ndhcp.odhcpd=odhcpd\\n' ;;
  esac ;;
  '-q get')
    case "$3" in
      network.wan6.proto) echo dhcpv6 ;;
      network.lte.proto) echo dhcp ;;
      dhcp.odhcpd.maindhcp) echo "$MASTER" ;;
    esac ;;
  'set '*|'commit '*|'-q delete') printf '%s\\n' "$*" >> "$TRACE" ;;
esac
''')
        create('ip', '''
if [ "$1" = -4 ]; then
  [ "$IPV4_OK" = 1 ] && echo 'default via 192.168.7.1 dev usb0 src 192.168.7.115 metric 5'
else
  echo ''
fi
''')
        create('sysctl', '''
if [ "$1" = -w ]; then
  echo "sysctl $2" >> "$TRACE"
  echo "$2"
elif [ "$1" = -n ]; then echo 1
fi
''')
        create('logger', ':')
        env={**os.environ,'PATH':str(path)+':'+os.environ['PATH'],
             'TRACE':str(path/'trace'),'IPV4_OK':'1' if ipv4 else '0',
             'MASTER':'1' if main_dhcp4 else '0'}
        return target, env, path/'trace'

    def test_apply_disables_all_network_and_dhcpv6_sections(self):
        with tempfile.TemporaryDirectory() as t:
            script,env,trace=self.fixture(t)
            p=subprocess.run(['sh',str(script),'apply'],env=env,
                             capture_output=True,text=True,timeout=6)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn('IPV4_ONLY=PASS',p.stdout)
            writes=trace.read_text()
            for item in ('network.lan.ipv6=0','network.lte.ipv6=0',
              'network.wan6.disabled=1','dhcp.lan.ra=disabled',
              'dhcp.guest.ra=disabled','dhcp.lan.dhcpv6=disabled',
              'dhcp.guest.ndp=disabled','commit network','commit dhcp',
              'sysctl net.ipv6.conf.all.disable_ipv6=1',
              'sysctl net.ipv6.conf.default.disable_ipv6=1',
              'sysctl net.ipv6.conf.lo.disable_ipv6=1',
              'odhcpd stop','odhcpd disable'):
                self.assertIn(item,writes,item)
            self.assertNotIn('network restart',writes)
            self.assertNotIn('ifdown',writes)

    def test_boot_defaults_do_not_require_ipv4_dhcp_yet(self):
        with tempfile.TemporaryDirectory() as t:
            script,env,trace=self.fixture(t,ipv4=False)
            p=subprocess.run(['sh',str(script),'apply-boot'],env=env,
                             capture_output=True,text=True,timeout=6)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn('IPV4_ONLY=PASS',p.stdout)
            self.assertIn('network.lan.ipv6=0',trace.read_text())

    def test_refuse_when_ipv4_wan_missing(self):
        with tempfile.TemporaryDirectory() as t:
            script,env,trace=self.fixture(t,ipv4=False)
            p=subprocess.run(['sh',str(script),'apply'],env=env,
                             capture_output=True,text=True,timeout=6)
            self.assertNotEqual(p.returncode,0)
            self.assertFalse(trace.exists(),'Unsafe configuration mutation despite failed IPv4 preflight')

    def test_odhcpd_not_stopped_if_running_dhcpv4(self):
        with tempfile.TemporaryDirectory() as t:
            script,env,trace=self.fixture(t,main_dhcp4=True)
            p=subprocess.run(['sh',str(script),'apply'],env=env,
                             capture_output=True,text=True,timeout=6)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertNotIn('odhcpd stop',trace.read_text())
            self.assertNotIn('odhcpd disable',trace.read_text())

if __name__=='__main__': unittest.main()
