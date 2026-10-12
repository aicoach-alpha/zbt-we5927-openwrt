"""SOURCE ONLY: sysfs/TTY identity verification with isolated simulated sysfs.

No physical /sys, /dev/ttyUSB, USB ioctls, modem commands, or network access.
"""
import ctypes
import os
from pathlib import Path
import pty
import subprocess
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[1] / "source/we5927-lte/src"


class Identity(ctypes.Structure):
    _fields_ = [
        ("vendor_id", ctypes.c_uint),
        ("product_id", ctypes.c_uint),
        ("interface_number", ctypes.c_uint),
        ("tty_major", ctypes.c_uint),
        ("tty_minor", ctypes.c_uint),
    ]


class ModemIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        cls.so = str(Path(cls.build.name) / "libidentity.so")
        cc = subprocess.run(
            ["cc", "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
             "-fPIC", "-shared", str(SRC / "veci-modem-identity.c"),
             "-o", cls.so], capture_output=True, text=True)
        if cc.returncode:
            raise AssertionError(cc.stderr)
        cls.lib = ctypes.CDLL(cls.so)
        cls.lib.veci_modem_verify_identity.argtypes = [
            ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int,
            ctypes.POINTER(Identity)]
        cls.lib.veci_modem_verify_identity.restype = ctypes.c_int

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "simulated-sys"
        self.root.mkdir()
        self.tty = "ttyUSB2"
        self.interface = "1-1:1.4"
        self.device = self.root / "devices/usb1/1-1"
        self.serial = self.device / self.interface / self.tty
        self.serial.mkdir(parents=True)
        self.classdir = self.root / "class/tty" / self.tty
        self.classdir.mkdir(parents=True)
        self.master, self.slave = pty.openpty()
        self._link_to(self.classdir / "device", self.serial)
        self._build_driver("option1")
        self._attr(self.device / "idVendor", "05c6\n")
        self._attr(self.device / "idProduct", "902e\n")
        d = os.fstat(self.slave).st_rdev
        self._attr(self.classdir / "dev", f"{os.major(d)}:{os.minor(d)}\n")

    def tearDown(self):
        os.close(self.slave)
        os.close(self.master)
        self.tmp.cleanup()

    @staticmethod
    def _attr(file, text):
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)

    @staticmethod
    def _link_to(link, dst):
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink():
            link.unlink()
        link.symlink_to(os.path.relpath(dst, link.parent))

    def _build_driver(self, name):
        link = self.device / self.interface / "driver"
        dst = self.root / "bus/usb-serial/drivers" / name
        dst.mkdir(parents=True, exist_ok=True)
        self._link_to(link, dst)

    def verify(self, tty=None, fd=None, root=None):
        out = Identity(100, 100, 100, 100, 100)
        rc = self.lib.veci_modem_verify_identity(
            str(root or self.root).encode(),
            (self.tty if tty is None else tty).encode(),
            self.slave if fd is None else fd, ctypes.byref(out))
        if rc != 0:
            self.assertEqual(out.vendor_id, 0)
            self.assertEqual(out.product_id, 0)
            self.assertEqual(out.interface_number, 0)
        return rc, out

    def test_verified_vendor_product_driver_interface_and_live_fd(self):
        rc, out = self.verify()
        self.assertEqual(rc, 0)
        self.assertEqual((out.vendor_id, out.product_id, out.interface_number),
                         (0x05c6, 0x902e, 4))
        self.assertEqual(out.tty_major, os.major(os.fstat(self.slave).st_rdev))

    def test_resolved_alternate_valid_driver_option(self):
        self._build_driver("option")
        self.assertEqual(self.verify()[0], 0)

    def test_reject_nonserial_file_descriptor(self):
        with tempfile.TemporaryFile() as f:
            self.assertNotEqual(self.verify(fd=f.fileno())[0], 0)

    def test_reject_missing_or_closed_fd(self):
        self.assertNotEqual(self.verify(fd=-1)[0], 0)
        self.assertNotEqual(self.verify(fd=12345678)[0], 0)

    def test_reject_ttyusb3_even_if_interface_matches(self):
        self.tty = "ttyUSB3"
        self.classdir = self.root / "class/tty" / self.tty
        self.classdir.mkdir(parents=True)
        self.serial = self.device / self.interface / self.tty
        self.serial.mkdir()
        self._link_to(self.classdir / "device", self.serial)
        d = os.fstat(self.slave).st_rdev
        self._attr(self.classdir / "dev", f"{os.major(d)}:{os.minor(d)}")
        self.assertNotEqual(self.verify()[0], 0)

    def test_reject_unsafe_tty_names_and_path_traversal(self):
        for name in ("ttyUSB", "ttyUSBx", "ttyUSB2/../ttyUSB3",
                     "../../ttyUSB2", "ttyUSB02x", "ttyS0",
                     "ttyUSB2\n", "ttyUSB999999", "ttyUSB-1"):
            with self.subTest(name=name):
                self.assertNotEqual(self.verify(tty=name)[0], 0)

    def test_wrong_vendor_fails_closed(self):
        self._attr(self.device / "idVendor", "12d1\n")
        self.assertNotEqual(self.verify()[0], 0)

    def test_wrong_product_fails_closed(self):
        self._attr(self.device / "idProduct", "902f\n")
        self.assertNotEqual(self.verify()[0], 0)

    def test_corrupt_vid_pid_fails_closed(self):
        for field in ("idVendor", "idProduct"):
            with self.subTest(field=field):
                original = (self.device / field).read_text()
                self._attr(self.device / field, "0x05c6\n")
                self.assertNotEqual(self.verify()[0], 0)
                self._attr(self.device / field, original)

    def test_missing_vendor_attribute_fails_closed(self):
        (self.device / "idVendor").unlink()
        self.assertNotEqual(self.verify()[0], 0)

    def test_symlinked_vendor_attribute_fails_closed(self):
        (self.device / "idVendor").unlink()
        target = self.root / "external-idVendor"
        target.write_text("05c6\n")
        self._link_to(self.device / "idVendor", target)
        self.assertNotEqual(self.verify()[0], 0)

    def test_malicious_interface_one_point_five_is_rejected(self):
        self.serial = self.device / "1-1:1.5" / self.tty
        self.serial.mkdir(parents=True)
        self._link_to(self.classdir / "device", self.serial)
        self.assertNotEqual(self.verify()[0], 0)

    def test_nearly_matching_interface_is_rejected(self):
        self.serial = self.device / "x1-1:1.40" / self.tty
        self.serial.mkdir(parents=True)
        self._link_to(self.classdir / "device", self.serial)
        self.assertNotEqual(self.verify()[0], 0)

    def test_traversal_to_outside_fake_sysfs_is_rejected(self):
        escaped = Path(self.tmp.name) / "outside-sysfs" / self.tty
        escaped.mkdir(parents=True)
        self._link_to(self.classdir / "device", escaped)
        self.assertNotEqual(self.verify()[0], 0)

    def test_bad_usb_driver_rejected(self):
        self._build_driver("rndis_host")
        self.assertNotEqual(self.verify()[0], 0)

    def test_driver_symlink_outside_root_is_rejected(self):
        link = self.device / self.interface / "driver"
        dst = Path(self.tmp.name) / "outside-driver"
        dst.mkdir()
        self._link_to(link, dst)
        self.assertNotEqual(self.verify()[0], 0)

    def test_missing_driver_rejected(self):
        (self.device / self.interface / "driver").unlink()
        self.assertNotEqual(self.verify()[0], 0)

    def test_major_minor_mismatch_rejected(self):
        self._attr(self.classdir / "dev", "188:2\n")
        self.assertNotEqual(self.verify()[0], 0)

    def test_major_minor_bad_syntax_rejected(self):
        for text in ("136:-1", "136:1 garbage", "136", "x:y", "136:42949672960",
                     "136:1\nother", "136:"):
            with self.subTest(text=text):
                self._attr(self.classdir / "dev", text)
                self.assertNotEqual(self.verify()[0], 0)

    def test_symlinked_dev_attribute_rejected(self):
        d = self.classdir / "dev"
        val = d.read_text()
        d.unlink()
        dst = self.root / "outside-dev"
        dst.write_text(val)
        self._link_to(d, dst)
        self.assertNotEqual(self.verify()[0], 0)

    def test_missing_tty_class_symlink_rejected(self):
        (self.classdir / "device").unlink()
        self.assertNotEqual(self.verify()[0], 0)

    def test_alternate_sysfs_tty_subtree_layout(self):
        nested = self.device / self.interface / self.tty / "tty" / self.tty
        nested.mkdir(parents=True)
        self._link_to(self.classdir / "device", nested)
        self.assertEqual(self.verify()[0], 0)

    def test_no_io_or_actual_modem_access_in_source(self):
        s = (SRC / "veci-modem-identity.c").read_text()
        self.assertNotIn("/dev/ttyUSB", s)
        self.assertNotIn("AT+CM", s)
        for token in ("write(", "tcsetattr(", "ioctl(", "syslog(",
                      "socket(", "fork(", "system("):
            self.assertNotIn(token, s)


if __name__ == "__main__":
    unittest.main()
