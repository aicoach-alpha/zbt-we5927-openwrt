"""A modem response may be split across USB reads independently of AT lines."""
import os
from pathlib import Path
import select
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class TerminalLines(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.binary = Path(cls.tmp.name) / "we5927-at"
        subprocess.run(["cc", "-Wall", "-Wextra", "-Werror", "-o", cls.binary,
                        ROOT / "source/we5927-lte/src/we5927-at.c"], check=True)

    def response(self, chunks):
        master, slave = os.openpty()
        try:
            with subprocess.Popen([self.binary, os.ttyname(slave), "AT", "1200"],
                                  stdout=subprocess.PIPE) as proc:
                self.assertTrue(select.select([master], [], [], 2)[0])
                self.assertEqual(os.read(master, 512), b"AT\r")
                for chunk in chunks:
                    os.write(master, chunk)
                    self.assertTrue(select.select([proc.stdout], [], [], 2)[0])
                    self.assertEqual(os.read(proc.stdout.fileno(), 4096), chunk)
                return proc.wait(timeout=2)
        finally:
            os.close(master)
            os.close(slave)

    def test_split_success(self):
        self.assertEqual(self.response([b"\r\nO", b"K\r\n"]), 0)

    def test_information_can_contain_error_word(self):
        self.assertEqual(self.response([b'\r\n+CEER: LAST ERROR\r\n', b'\r\nOK\r\n']), 0)

    def test_split_modem_error(self):
        self.assertEqual(self.response([b'\r\n+CM', b'E ERROR: 10\r\n']), 1)
