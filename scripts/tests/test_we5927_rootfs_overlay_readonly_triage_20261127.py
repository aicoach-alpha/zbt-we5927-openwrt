"""Real BusyBox ash/data tests for non-destructive live MTD3/overlay triage."""
import hashlib
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/veci-we5927-readonly-rootfs-overlay-triage-20261127.ps1"
M3 = 0x7a0000
M4 = 0x1dc72d
M5 = 0x5c38d3
M6 = 0x220000
PREFIX = M3 - M6

class RootfsOverlayTriage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SCRIPT.read_text(encoding="utf-8")
        part = re.search(r"(?ms)^\$script = @'\n(.*?)\n'@", cls.text)
        assert part, "Expected source-owned, literal POSIX read-only script"
        cls.shell = part.group(1)
        assert shutil.which("busybox"), "BusyBox shell needed, do not use bash as a substitute"

    def fixture(self, dirname, altered_overlay=False, bad_layout=False):
        work = Path(dirname)
        board = work / "board_name"
        board.write_text("zbtlink,zbt-we5927\n")
        mtd = work / "mtd"
        if bad_layout:
            mtd.write_text(
                "dev: size erasesize name\n"
                "mtd3: 007a0000 00010000 \"firmware\"\n"
                "mtd4: 001dc72d 00010000 \"kernel\"\n"
                "mtd5: 005c38d3 00010000 \"rootfs\"\n"
                "mtd6: 00220000 00010000 \"wrong_name\"\n"
            )
        else:
            mtd.write_text(
                "dev: size erasesize name\n"
                "mtd3: 007a0000 00010000 \"firmware\"\n"
                "mtd4: 001dc72d 00010000 \"kernel\"\n"
                "mtd5: 005c38d3 00010000 \"rootfs\"\n"
                "mtd6: 00220000 00010000 \"rootfs_data\"\n"
            )
        parent = (b"K" * M4) + (b"R" * (PREFIX - M4)) + (b"O" * M6)
        assert len(parent) == M3 and M4 + M5 == M3
        files = {
            "mtd3": parent,
            "mtd4": parent[:M4],
            "mtd5": parent[M4:],
            "mtd6": (b"X" * M6 if altered_overlay else parent[-M6:]),
        }
        for name, payload in files.items():
            (work / name).write_bytes(payload)
        body = self.shell.replace("/tmp/sysinfo/board_name", str(board)).replace("/proc/mtd", str(mtd))
        for name in ("mtd3", "mtd4", "mtd5", "mtd6"):
            body = body.replace("/dev/" + name, str(work / name))
        return 'dd() { busybox dd "$@"; }\n' + body, parent

    def test_real_busybox_remote_ash_syntax(self):
        subprocess.run(["busybox", "ash", "-n"], input=self.shell, text=True, check=True, timeout=8)

    def test_real_mtd_partition_overlay_alias_and_prefix_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, parent = self.fixture(tmp)
            p = subprocess.run(["busybox", "ash", "-c", code], capture_output=True, text=True, timeout=20)
            self.assertEqual(p.returncode, 0, p.stderr)
            output = dict(row.split("=", 1) for row in p.stdout.splitlines() if "=" in row)
            self.assertEqual(int(output["LIVE_MTD3_BYTES"]), M3)
            self.assertEqual(int(output["LIVE_MTD4_KERNEL_BYTES"]), M4)
            self.assertEqual(int(output["LIVE_MTD5_ROOTFS_BYTES"]), M5)
            self.assertEqual(int(output["LIVE_MTD6_OVERLAY_BYTES"]), M6)
            self.assertEqual(int(output["LIVE_PRE_OVERLAY_PREFIX_BYTES"]), PREFIX)
            self.assertEqual(output["LIVE_MTD4_KERNEL_SHA256"], hashlib.sha256(parent[:M4]).hexdigest())
            self.assertEqual(output["LIVE_MTD3_PRE_OVERLAY_SHA256"], hashlib.sha256(parent[:PREFIX]).hexdigest())
            self.assertEqual(output["LIVE_MTD6_OVERLAY_SHA256"], hashlib.sha256(parent[-M6:]).hexdigest())
            self.assertEqual(output["LIVE_MTD3_TAIL_SHA256"], output["LIVE_MTD6_OVERLAY_SHA256"])
            self.assertEqual(output["ROOTFS_OVERLAY_LAYOUT_HASHES_READ_ONLY_DONE"], "YES")
            # Different aggregate hashes can coexist with identical kernel+base prefix.
            old = parent[:PREFIX] + b"Q" * M6
            self.assertNotEqual(hashlib.sha256(old).digest(), hashlib.sha256(parent).digest())
            self.assertEqual(hashlib.sha256(old[:PREFIX]).digest(), hashlib.sha256(parent[:PREFIX]).digest())

    def test_mtd6_not_parent_tail_does_not_look_like_verified_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _ = self.fixture(tmp, altered_overlay=True)
            p = subprocess.run(["busybox", "ash", "-c", code], capture_output=True, text=True, timeout=20)
            self.assertEqual(p.returncode, 0, p.stderr)
            output = dict(row.split("=", 1) for row in p.stdout.splitlines() if "=" in row)
            self.assertNotEqual(output["LIVE_MTD3_TAIL_SHA256"], output["LIVE_MTD6_OVERLAY_SHA256"])
            self.assertIn("NOT_VERIFIED_LAYOUT_ALIAS", self.text)
            self.assertIn("ROOTFS_DATA_IS_PARENT_TAIL", self.text)

    def test_incomplete_parent_reads_do_not_produce_a_comparison(self):
        for size, reason in ((PREFIX - 1, "PREFIX"), (M3 - 65536, "TAIL")):
            with self.subTest(size=size), tempfile.TemporaryDirectory() as tmp:
                code, _ = self.fixture(tmp)
                with (Path(tmp) / "mtd3").open("rb+") as parent:
                    parent.truncate(size)
                result = subprocess.run(["busybox", "ash", "-c", code], capture_output=True, text=True, timeout=20)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("STOP=INCOMPLETE_PARENT_" + reason, result.stderr)
                self.assertNotIn("ROOTFS_OVERLAY_LAYOUT_HASHES_READ_ONLY_DONE=YES", result.stdout)

    def test_malformed_partition_map_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _ = self.fixture(tmp, bad_layout=True)
            p = subprocess.run(["busybox", "ash", "-c", code], capture_output=True, text=True, timeout=10)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("STOP=PARTITION_LAYOUT_NOT_SUPPORTED", p.stderr)
            self.assertNotIn("ROOTFS_OVERLAY_LAYOUT_HASHES_READ_ONLY_DONE=YES", p.stdout)

    def test_no_firmware_mutation_and_archive_integrity_verification(self):
        for forbidden in (r"\b(?:mtd\s+(?:write|erase)|flash_erase|sysupgrade|reboot|uci\s+(?:set|commit)|wifi\s+(?:reload|up|down)|ubus\s+call|killall|chmod)\b",
                          r"\bdd\s+of=", r"\bmount\s+", r"\brm\s+-"):
            self.assertIsNone(re.search(forbidden, self.shell, flags=re.I), forbidden)
        for required in (
                "StrictHostKeyChecking=yes", "root@192.168.1.1",
                "STOP=ARCHIVE_SHA256_CHANGED_", "Get-FileHash -LiteralPath",
                "Get-SegmentSha256", "LIVE_MTD4_KERNEL_SHA256",
                "LIVE_MTD3_PRE_OVERLAY_SHA256", "STOP=REMOTE_LAYOUT_INCONSISTENT",
                "bootloader_restore_test='NOT_RUN'", "flash_authorized=$false",
                "ROOTFS_OVERLAY_TRIAGE_COMPLETE=YES"):
            self.assertIn(required, self.text)
        self.assertNotIn("Get-Content -LiteralPath $f -Raw", self.text)

if __name__ == "__main__":
    unittest.main()
