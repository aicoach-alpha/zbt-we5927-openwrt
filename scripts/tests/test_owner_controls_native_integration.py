import json
import re
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
PACKAGES=ROOT/"rebuild/veci-v2/packages"
RUNTIME=PACKAGES/"veci-v2-runtime"
UI=PACKAGES/"veci-v2-ui"
HTML=(UI/"files/www/veci2/index.html").read_text()
JS=(UI/"files/www/veci2/owner-controls.js").read_text()
APP=(UI/"files/www/veci2/app.js").read_text()


class IdParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=set()
    def handle_starttag(self, tag, attrs):
        self.ids.update(v for k,v in attrs if k=="id")


class NativeOwnerControlsIntegration(unittest.TestCase):
    def test_provider_files_installed_and_acl_typed(self):
        runtime=(RUNTIME/"Makefile").read_text()
        acl=json.loads((RUNTIME/"veci2-status-acl.json").read_text())
        providers={
            "veci2-static-leases":("veci.v2.dhcp","veci-v2-dhcp",["status"],["add","delete"]),
            "veci2-sim-manual":("veci.v2.sim","veci-v2-sim",["status"],["switchSim"]),
            "veci2-firewall":("veci.v2.firewall","veci-v2-firewall",["status"],["addForward","deleteForward","setDmz"]),
            "veci2-system-admin":("veci.v2.system","veci-v2-system",["ntp","logs","leds","observability"],["setNtp"])
        }
        for filename,(rpc,key,reads,writes) in providers.items():
            with self.subTest(provider=filename):
                file=RUNTIME/filename
                self.assertTrue(file.is_file())
                self.assertIn(f"./{filename} $(1)/usr/libexec/rpcd/{rpc}",runtime)
                self.assertEqual(acl[key]["read"]["ubus"][rpc],reads)
                self.assertEqual(acl[key]["write"]["ubus"][rpc],writes)
                p=subprocess.run(["sh","-n",str(file)],capture_output=True,text=True)
                self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn("veci2-status-acl.json",runtime)

    def test_gui_hooks_valid_and_authenticated(self):
        parser=IdParser();parser.feed(HTML)
        ids=set(re.findall(r"el\('([^']+)'\)",JS))
        self.assertFalse(ids-parser.ids,sorted(ids-parser.ids))
        self.assertIn('owner-controls.js',HTML)
        self.assertIn("VeciOwnerControls?.init",APP)
        self.assertIn("VeciOwnerControls?.logout",APP)
        self.assertIn("VeciOwnerControls?.refreshNetwork",APP)
        self.assertIn("VeciOwnerControls?.refreshSettings",APP)
        self.assertIn("owner-controls.js",(UI/"Makefile").read_text())
        self.assertIn("window.confirm",JS)
        self.assertIn("if (!authenticated() || !rpc)",JS)
        self.assertNotIn("localStorage",JS)
        self.assertNotIn("sessionStorage",JS)
        self.assertNotIn("innerHTML",JS)
        for file in ("app.js","owner-controls.js"):
            p=subprocess.run(["node","--check",str(UI/"files/www/veci2"/file)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)

    def test_group_navigation_remains_simple(self):
        self.assertEqual(HTML.count('class="tab"'),3)
        self.assertEqual(HTML.count('class="tab active"'),1)
        self.assertGreater(HTML.count("<details>"),3)
        self.assertIn("SMS Center",HTML)

    def test_firewall_shows_owner_named_rules(self):
        fw=(RUNTIME/"veci2-firewall").read_text()
        self.assertIn("veci_port_(tcp|udp)",fw)
        self.assertIn("dmz_destination",fw)
        self.assertIn("firewall.veci_owner_dmz.dest_ip",fw)


class ValidatorBehaviors(unittest.TestCase):
    @staticmethod
    def check(script, fn, testval, wanted):
        text=(RUNTIME/script).read_text().split('[ "$#" -ge 1 ] || fail unsupported_method')[0]
        proc=subprocess.run(["sh","-c",text+fn+' "$1"',"validation",testval],capture_output=True,text=True,timeout=5)
        assert (proc.returncode==0)==wanted, f"{script} {fn} {testval}: {proc.returncode} {proc.stderr}"

    def test_dhcp_static_validators(self):
        for ip,ok in [
            ("192.168.1.20",True),("10.0.0.1",True),("0.0.0.0",False),
            ("127.0.0.1",False),("224.0.0.1",False),("256.2.2.2",False),
            ("1.1.1.01",False),("1.1.1",False),("1.1..1",False),
            ("1.1.1.1; reboot",False)]:
            with self.subTest(ip=ip): self.check("veci2-static-leases","valid_ip",ip,ok)
        for mac,ok in [
            ("aa:bb:cc:dd:ee:ff",True),("AA:BB:CC:DD:EE:FF",True),
            ("aa-bb-cc-dd-ee-ff",False),("aa:bb:cc:dd:ee",False),
            ("aa:bb:cc:dd:ee:ff;evil",False)]:
            with self.subTest(mac=mac): self.check("veci2-static-leases","valid_mac",mac,ok)

    def test_firewall_port_and_ip_validators(self):
        for port,ok in [
            ("1",True),("80",True),("65535",True),("0",False),
            ("65536",False),("01",False),("22; reboot",False),("-1",False)
        ]:
            with self.subTest(port=port): self.check("veci2-firewall","valid_port",port,ok)
        for ip,ok in [
            ("192.168.1.20",True),("0.0.0.0",False),("255.255.255.255",False),
            ("1.1.1",False),("01.1.1.1",False)
        ]:
            with self.subTest(fw_ip=ip): self.check("veci2-firewall","valid_ipv4",ip,ok)

    def test_ntp_hostname_rejections(self):
        for host,ok in [
            ("pool.ntp.org",True),("1.1.1.1",True),("time.google.com",True),
            ("",False),("-bad.example",False),(".example",False),
            ("example..com",False),("x; reboot",False),("bad port",False)
        ]:
            with self.subTest(host=host): self.check("veci2-system-admin","valid_host",host,ok)


if __name__=="__main__":
    unittest.main()
