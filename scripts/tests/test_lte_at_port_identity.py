"""Exercise the LTE manager against a synthetic sysfs and character-device tree."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
MANAGER = ROOT / "source/we5927-lte/files/usr/sbin/we5927-lte"


class AtPortIdentity(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.modem = self.root / "sys/devices/usb1/1-1"
        self.modem.mkdir(parents=True)
        (self.modem / "idVendor").write_text("05c6\n")
        (self.modem / "idProduct").write_text("902e\n")
        (self.root / "dev").mkdir()
        self.script = MANAGER.read_text()
        self.script = self.script.replace("/sys/", str(self.root) + "/sys/")
        self.script = self.script.replace("/dev/", str(self.root) + "/dev/")
        os.symlink("/dev/null", self.root / "dev/null")

    def tty(self, name, interface):
        device = self.modem / ("1-1:1." + interface) / name
        device.mkdir(parents=True)
        entry = self.root / "sys/class/tty" / name
        entry.mkdir(parents=True)
        (entry / "device").symlink_to(device)
        (self.root / "dev" / name).symlink_to("/dev/null")

    def resolve(self):
        return subprocess.run(["sh", "-c", self.script, "we5927-lte", "at-port"],
                              capture_output=True, text=True, timeout=4)

    def test_wrong_function_with_historical_name(self):
        self.tty("ttyUSB2", "5")
        result = self.resolve()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_renumbered_at_function(self):
        self.tty("ttyUSB2", "5")
        self.tty("ttyUSB7", "4")
        result = self.resolve()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.root / "dev/ttyUSB7"))

    def test_other_product_at_same_socket(self):
        self.tty("ttyUSB2", "4")
        (self.modem / "idProduct").write_text("ffff\n")
        self.assertNotEqual(self.resolve().returncode, 0)
