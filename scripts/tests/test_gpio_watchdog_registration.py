from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "rebuild/veci-v2/packages/veci-v2-runtime/veci2-gpio-watchdog"


class WatchdogRegistration(unittest.TestCase):
    def test_only_exact_board_controller_and_parameters_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            board = root / "board"
            board.write_text("zbtlink,zbt-we5927\n")
            script = SOURCE.read_text().replace("/sys/class/watchdog", tmp).replace("/tmp/sysinfo/board_name", str(board))
            def status():
                return subprocess.check_output(["sh", "-c", script], text=True).strip()
            self.assertIn("unconfirmed", status())
            wd = root / "watchdog1"
            node = wd / "device/of_node"
            node.mkdir(parents=True)
            (node / "compatible").write_bytes(b"linux,wdt-gpio\0")
            (node / "gpios").write_bytes(struct.pack(">III", 12, 37, 0))
            (node / "hw_algo").write_bytes(b"toggle\0")
            (node / "hw_margin_ms").write_bytes(struct.pack(">I",2000))
            (node / "always-running").touch()
            (wd / "state").write_text("active\n")
            self.assertEqual(status(), "gpio37_watchdog=registered\nkernel_state=active")
            (root / "watchdog2").symlink_to(wd)
            self.assertIn("ambiguous", status())
            (root / "watchdog2").unlink()
            (node / "gpios").write_bytes(struct.pack(">III", 12, 36, 0))
            self.assertIn("unconfirmed", status())
            board.write_text("unsupported\n")
            with self.assertRaises(subprocess.CalledProcessError):
                status()
