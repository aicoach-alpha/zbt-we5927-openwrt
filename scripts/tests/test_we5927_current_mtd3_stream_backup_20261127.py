"""Offline static safety contract for Windows binary stream backups (not router UAT)."""
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/"scripts/veci-we5927-current-mtd3-stream-backup-20261127.ps1"
class NoRawBinaryCorruptionOrRouterMutation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code=SOURCE.read_text()

    def test_router_only_reads_mtd3_and_never_writes_or_restarts(self):
        src=self.code
        for expected in ("dd if=/dev/mtd3 bs=65536 2>/dev/null",
                         "sha256sum /dev/mtd3",
                         "StrictHostKeyChecking=yes",
                         "root@192.168.1.1",
                         "7995392",
                         "LIVE_MTD3_HASH_BEFORE=CAPTURED",
                         "RAW-NOT-FLASHABLE",
                         "FLASH_AUTHORIZED=NO",
                         "router_tmpfs_file_created=$false",
                         "firmware_flash_authorized=$false",
                         "firmware_rollback_format_verified=$false"):
            self.assertIn(expected,src)
        for forbidden in ("mtd write", "mtd erase", "flash_erase",
                          "uci set", "uci commit", "wifi reload",
                          "dd of=/", "tftp", "scp.exe"):
            self.assertNotIn(forbidden,src.lower())
        executable_remote = [line for line in src.splitlines()
                             if ("& ssh.exe @arguments" in line or "$cli=" in line)]
        self.assertEqual(len(executable_remote), 2)
        for line in executable_remote:
            for forbidden in ("sysupgrade ", "reboot ", "mtd write", "mtd erase",
                              "flash_erase", "uci set", "dd of=", "wifi reload"):
                self.assertNotIn(forbidden,line.lower())
        self.assertEqual(src.count("dd if=/dev/mtd3"),1)

    def test_native_raw_bytes_not_powershell_redirect(self):
        src=self.code
        for key in ("RedirectStandardOutput=$true","$proc.StandardOutput.BaseStream.CopyTo($file)",
                    "FileMode]::CreateNew", "CURRENT_MTD3_BACKUP_SHA256_BEFORE_AND_AFTER=PASS",
                    "STOP=HASH_BEFORE_DIFFERS_FROM_SAVED_BACKUP",
                    "STOP=HASH_AFTER_DIFFERS_FROM_SAVED_BACKUP",
                    "STOP=RAW_MTD3_SIZE_MISMATCH",
                    "Get-FileHash -LiteralPath $temp", "if(Test-Path -LiteralPath $temp){Remove-Item"):
            self.assertIn(key,src)
        self.assertNotRegex(src,r"\b(?:ssh\.exe|ssh)\b.*\s>\s")

    def test_backup_side_effect_is_local_and_not_release_approval(self):
        src=self.code
        self.assertIn("D:\\Report_CCB",src)
        self.assertIn("BACKUP_COMPLETE=YES; ROUTER_NOT_MODIFIED=YES; FLASH_AUTHORIZED=NO",src)
        self.assertIn("current_installation_changed=$false" if "current_installation_changed=$false" in src else "router_rebooted=$false",src)
        self.assertIn("restore_procedure_tested=$false",src)
        self.assertIn("System.IO.File]::Move($temp,$final)",src)
        self.assertIn("ServerAliveInterval=10",src)
        self.assertIn("ServerAliveCountMax=2",src)
if __name__=="__main__": unittest.main()
