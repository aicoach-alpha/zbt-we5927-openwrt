import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class RndisIdentity(unittest.TestCase):
    def test_configured_network_must_belong_to_selected_modem(self):
        source = (Path(__file__).resolve().parents[2] / "files/usr/sbin/we5927-lte").read_text()
        functions = source[source.index("driver_name() {"):source.index("repair_rndis() {")]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            functions = functions.replace("/sys/class/net/", str(root / "net") + "/")
            script = 'cfg() { echo "$NET"; }; usb_device_dir() { echo "$MODEM"; };\n' + functions + '\nrndis_data_ready'
            def ready(name):
                env = dict(os.environ, NET=name, MODEM=str(root / "modem"))
                return subprocess.run(["sh", "-c", script], env=env).returncode == 0

            for name, parent, driver in (("usb1", "modem", "rndis_host"),
                                         ("usb0", "other", "rndis_host"),
                                         ("wwan0", "modem", "cdc_ether")):
                interface = root / parent / name
                interface.mkdir(parents=True)
                target = root / "drivers" / driver
                target.mkdir(parents=True, exist_ok=True)
                (interface / "driver").symlink_to(target)
                net = root / "net" / name
                net.mkdir(parents=True)
                (net / "device").symlink_to(interface)
            self.assertTrue(ready("usb1"))
            for name in ("usb0", "", "wwan0", "missing", "../modem"):
                with self.subTest(name=name):
                    self.assertFalse(ready(name))

    def test_cli_reports_usb_registration_binding_and_link(self):
        source = (Path(__file__).resolve().parents[2] / "files/usr/sbin/we5927-lte").read_text()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "lte"
            script.write_text(source.replace("/sys/bus/usb/devices", str(root / "usb"))
                              .replace("/sys/class/net", str(root / "net")))
            uci = root / "uci"
            uci.write_text("#!/bin/sh\nexit 1\n")
            uci.chmod(0o700)
            env = dict(os.environ, PATH=f"{root}:" + os.environ["PATH"])
            def state():
                return subprocess.check_output(["sh", script, "rndis-state"], env=env, text=True).strip()
            self.assertEqual(state(), "modem_missing")
            modem = root / "usb/1-1"
            modem.mkdir(parents=True)
            (modem / "idVendor").write_text("05c6")
            (modem / "idProduct").write_text("902e")
            self.assertEqual(state(), "interface_missing")
            interface = modem / "1-1:1.0"
            interface.mkdir()
            net = root / "net/usb0"
            net.mkdir(parents=True)
            (net / "device").symlink_to(interface)
            self.assertEqual(state(), "driver_mismatch")
            driver = root / "drivers/rndis_host"
            driver.mkdir(parents=True)
            (interface / "driver").symlink_to(driver)
            self.assertEqual(state(), "carrier_unknown usb0")
            for value, label in [("0", "down"), ("1", "up")]:
                (net / "carrier").write_text(value)
                self.assertEqual(state(), "carrier_" + label + " usb0")
            (net / "device").unlink()
            (net / "device").symlink_to(driver)
            self.assertEqual(state(), "other_device")
