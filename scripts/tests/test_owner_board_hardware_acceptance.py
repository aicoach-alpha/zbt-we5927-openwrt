"""Source-level WE2825 device-tree LED/reset GPIO and external watchdog proof.

Runs real read-only probe over a fake sysfs tree; never opens /dev/watchdog,
toggles a pin, or declares physical board behavior validated.
"""
import json,os,re,struct,subprocess,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DTS=ROOT/"source/mt7628an_zbtlink_zbt-we5927.dts"
WDT=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime/veci2-gpio-watchdog"
STATUS=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime/veci2-watchdog-status"
ACL=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime/veci2-watchdog-acl.json"
SYSTEM=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime/veci2-system-admin"
CONFIG=ROOT/"source/openwrt-we5927.config"

class BoardHardwareAcceptance(unittest.TestCase):
    def test_exact_oem_gpio37_reset38_lan_leds_and_sim46_not_confused(self):
        s=DTS.read_text()
        self.assertIn('compatible = "zbtlink,zbt-we5927", "mediatek,mt7628an-soc"',s)
        self.assertIsNotNone(re.search(r'reset\s*\{.*?gpio 38 GPIO_ACTIVE_LOW',s,re.S))
        self.assertIsNotNone(re.search(r'watchdog\s*\{.*?compatible = "linux,wdt-gpio";.*?gpio 37 GPIO_ACTIVE_HIGH',s,re.S))
        self.assertIn('hw_algo = "toggle"',s)
        self.assertIn('hw_margin_ms = <2000>',s)
        self.assertIn('always-running;',s)
        leds=dict(re.findall(r'(lan1|lan2|lan3|wan|led_wlan:\s*wlan2g)\s*\{\s*gpios = <&gpio (\d+)',s))
        self.assertEqual({k.replace('led_wlan:  ','').replace('led_wlan: ','').strip():v for k,v in leds.items()},
                         {'lan1':'43','lan2':'42','lan3':'41','wan':'39','wlan2g':'44'})
        self.assertIn('gpio 46 GPIO_ACTIVE_LOW',s)
        self.assertEqual(len({37,38,39,41,42,43,44,46}),8)
        c=CONFIG.read_text()
        self.assertIn("CONFIG_PACKAGE_kmod-gpio-button-hotplug=y",c)
        self.assertIn("CONFIG_PACKAGE_kmod-leds-gpio=y",c)

    def test_sysfs_watchdog_probe_matches_only_expected_gpio37(self):
        with tempfile.TemporaryDirectory(prefix="veci-wdt-hw-") as directory:
            t=Path(directory);board=t/"board";board.write_text("zbtlink,zbt-we5927\n")
            script=WDT.read_text().replace("/tmp/sysinfo/board_name",str(board))
            script=script.replace("/sys/class/watchdog/",str(t)+"/")
            wd=t/"watchdog0/device/of_node"
            wd.mkdir(parents=True)
            (wd/"compatible").write_bytes(b"linux,wdt-gpio\0")
            (wd/"gpios").write_bytes(struct.pack(">III", 1, 37, 0))
            (wd/"hw_algo").write_bytes(b"toggle\0")
            (wd/"hw_margin_ms").write_bytes(struct.pack(">I",2000))
            (wd/"always-running").touch()
            (t/"watchdog0/state").write_text("active\n")
            assert_p=subprocess.run(["busybox","ash","-c",script],capture_output=True,text=True,timeout=7)
            self.assertEqual(assert_p.returncode,0,assert_p.stderr)
            self.assertIn("gpio37_watchdog=registered",assert_p.stdout)
            self.assertIn("kernel_state=active",assert_p.stdout)
            (wd/"gpios").write_bytes(struct.pack(">III", 1, 46, 0))
            result=subprocess.run(["busybox","ash","-c",script],capture_output=True,text=True,timeout=7)
            self.assertIn("gpio37_watchdog=unconfirmed",result.stdout)

    def test_readonly_watchdog_status_rpc_uses_registered_helper(self):
        with tempfile.TemporaryDirectory(prefix="veci-wdt-rpc-") as directory:
            t=Path(directory);board=t/"board";board.write_text("zbtlink,zbt-we5927\n")
            helper=t/"probe";helper.write_text("""#!/bin/sh
echo gpio37_watchdog=registered
echo kernel_state=active
""")
            helper.chmod(0o755)
            program=t/"status"
            program.write_text(STATUS.read_text()
                .replace("/tmp/sysinfo/board_name",str(board))
                .replace("/usr/libexec/veci2-gpio-watchdog",str(helper)))
            for status,state in (("registered","active"),("unconfirmed","unknown"),("ambiguous","unknown")):
                helper.write_text("#!/bin/sh\necho gpio37_watchdog="+status+"\n"+
                                  ("echo kernel_state="+state+"\n" if state!="unknown" else ""))
                r=subprocess.run(["busybox","ash",str(program),"call","status"],
                        text=True,capture_output=True,timeout=6)
                self.assertEqual(r.returncode,0,r.stderr)
                payload=json.loads(r.stdout)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["registration"],status)
                self.assertEqual(payload["kernel_state"],state)
                self.assertEqual(payload["proof"],"kernel_sysfs_read_only")
            board.write_text("other-board\n")
            r=subprocess.run(["busybox","ash",str(program),"call","status"],text=True,capture_output=True,timeout=4)
            self.assertEqual(json.loads(r.stdout)["error"],"unsupported_board")
            acl=json.loads(ACL.read_text())["veci-v2-watchdog-observe"]
            self.assertEqual(acl["read"]["ubus"]["veci.v2.watchdog"],["status"])
            self.assertEqual(acl["write"]["ubus"],{})
            for text in (WDT.read_text(),STATUS.read_text()):
                for forbidden in ("/dev/watchdog", "gpio_set", "reboot", "AT+CFUN", "ifdown"):
                    if forbidden=="/dev/watchdog":
                        self.assertNotIn("cat /dev/watchdog",text)
                    else:
                        self.assertNotIn(forbidden,text)

    def test_led_button_runtime_uses_kernel_sysfs_and_no_gpio_writes(self):
        s=SYSTEM.read_text()
        self.assertIn("/sys/class/leds/*",s)
        self.assertIn("json_add_string brightness",s)
        self.assertNotIn("echo 0 > /sys/class/leds",s)
        self.assertNotIn("echo 1 > /sys/class/leds",s)
        self.assertIn('keys {',DTS.read_text())
        self.assertIn('linux,code = <KEY_RESTART>',DTS.read_text())
        subprocess.run(["busybox","ash","-n",str(SYSTEM)],check=True,capture_output=True,timeout=5)

if __name__=="__main__":unittest.main()
