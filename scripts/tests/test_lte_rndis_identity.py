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
