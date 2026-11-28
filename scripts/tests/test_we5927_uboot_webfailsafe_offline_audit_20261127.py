"""Require offline-only mtd0 inspection and fail-closed historical fingerprints."""
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'scripts/veci-we5927-uboot-webfailsafe-offline-audit-20261127.ps1'

class UBootOfflineEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=SCRIPT.read_text()

    def test_exact_five_partition_history_gate_and_mtd0_integrity(self):
        s=self.source
        for token in (
          "we5927-local-recovery-audit.v1",
          "b2acbf1e762e310d467cfcbae853257a9f63ce311511134bc9d0d5953f835330",
          "196608","mtd0", "NOV23", "NOV25", "HISTORICAL_SHA_PASS",
          "SIZE_PASS_HASH_RECORDED_NOT_ROUTER_MATCHED", "Get-FileHash -LiteralPath",
          "STOP=MTD0_BINARY_SHA_MISMATCH_",
          "EXACT_MTD0_NOV23_AND_NOV25_SHA256=PASS",
          "STOP=MARKER_OFFSETS_DIFFER_DESPITE_MTD0_IDENTICAL_SHA_"):
            self.assertIn(token,s)

    def test_statically_detected_http_upload_is_flagged_dangerous(self):
        s=self.source
        for token in (
          'HTTP_SERVER_START','HTTP_SERVER_READY','WEB_FAILSAFE_MENU',
          'RESET_UPDATE_MODE','HTTP_FIRMWARE_FORM','MT76X8_UPDATE_PAGE',
          'UPLOAD_TRIGGERS_UPGRADE','TFTP_COMMAND','U-Boot',
          'HTTP upload is done! Upgrading',
          'DANGER=HTTP_FIRMWARE_UPLOAD_MAY_TRIGGER_IMMEDIATE_FLASH'):
            self.assertIn(token,s)
        self.assertIn("BOOTLOADER_RESCUE_FORMAT=NOT_VERIFIED",s)
        self.assertIn("PHYSICAL_RECOVERY_ENTRY=NOT_TESTED",s)
        self.assertIn("UPLOAD_ACCEPTANCE=NOT_TESTED",s)
        self.assertIn("flash_authorized=$false",s)
        self.assertIn("code_strings_are_not_runtime_capability=$true",s)

    def test_script_has_no_router_communication_or_writes(self):
        s=self.source
        # Comments may describe dangers, so inspect executable/statement lines.
        executable='\n'.join(line for line in s.splitlines() if not line.lstrip().startswith('#'))
        for forbidden in (
          r'\bssh(?:\.exe)?\b',r'\bscp(?:\.exe)?\b',
          r'\bsysupgrade\s+',r'\bmtd\s+(?:write|erase)\b',
          r'\bflash_erase\b',r'\buci\s+(?:set|commit)\b',
          r'\breboot\s+',r'\bInvoke-WebRequest\b',
          r'\bcurl(?:\.exe)?\b',r'\bInvoke-RestMethod\b',
          r'\bStart-Process\b'):
            self.assertIsNone(re.search(forbidden,executable,flags=re.I),forbidden)
        self.assertIn("ReadAllBytes($backupPaths[$generation])",s)
        self.assertIn("ROUTER_NOT_CONTACTED=YES",s)
        self.assertIn("NO_FIRMWARE_UPLOAD_PERFORMED=YES",s)

if __name__=='__main__':
    unittest.main()
