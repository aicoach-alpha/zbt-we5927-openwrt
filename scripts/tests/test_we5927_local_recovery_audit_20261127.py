"""Safety contract for local-only Windows MTD recovery audit; not a hardware UAT."""
from pathlib import Path
import re
import unittest
ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"scripts/veci-we5927-mtd-recovery-audit-Windows-20261127.ps1"

class RecoveryAuditOnly(unittest.TestCase):
    def test_script_limits_scope_to_local_files_without_router_commands(self):
        s=SCRIPT.read_text()
        for marker in ("LOCAL_READ_ONLY","SSH=NONE","ROUTER_ACCESS=NONE",
                       "FLASH=NO","NO_ROUTER_CONTACT","FIRMWARE_FLASH_AUTHORIZED=NO",
                       "CURRENT_ROUTER_MTD_EQUALS_BACKUP=NOT_TESTED",
                       "LIVE_BOOTLOADER_RECOVERY=NOT_TESTED",
                       "flash_authorized=$false"):
            self.assertIn(marker,s)
        for forbidden in (r"\bssh(?:\.exe)?\s+-",r"\bscp(?:\.exe)?\s+-",r"\bsysupgrade\s+",
                          r"\bflash_erase\b",r"\bmtd\s+(?:write|erase)\b",
                          r"\breboot\s+",r"\bInvoke-Expression\b",r"\bStart-Process\b",
                          r"\bSet-Service\b"):
            self.assertIsNone(re.search(forbidden,s,flags=re.I),forbidden)
    def test_expected_exact_backup_partition_bytes_and_known_source_hashes(self):
        s=SCRIPT.read_text()
        checks={0:(196608,"b2acbf1e762e310d467cfcbae853257a9f63ce311511134bc9d0d5953f835330"),
                1:(65536,"757def42b82e074ebf0638d7f45fbbc3d0caf406958225685fea8af423745977"),
                2:(65536,"65442ad13e9e4795004f16ede40718d0fbf7d8eb07d8702ba3b1e410fee951f7"),
                3:(7995392,"6a75b2b3e0db3782c3d3b66908395026840033319705c99ee9391637202528bd"),
                7:(65536,"f143aeb1d2fed906e4d0d88268251083cd4326fa05f66b1c2283834cf973dba9")}
        for idx,(size,sha) in checks.items():
            self.assertRegex(s,rf"Index={idx}; Bytes={size};.+Sha23='{sha}'")
        self.assertIn("Get-FileHash -LiteralPath",s)
        self.assertIn("HISTORICAL_SHA_PASS",s)
        self.assertIn("SIZE_PASS_HASH_RECORDED_NOT_ROUTER_MATCHED",s)
        self.assertIn("AMBIGUOUS_FILES",s)
        self.assertIn("HISTORICAL_SHA_MISMATCH",s)
    def test_windows_paths_and_report_are_local(self):
        s=SCRIPT.read_text()
        self.assertIn("D:\\Report_CCB",s)
        self.assertIn("VeCI-WE5927-Recovery-20261123-171236",s)
        self.assertIn("WE5927-Recovery-20261125_135411",s)
        self.assertIn("WE5927-RECOVERY-AUDIT-",s)
        self.assertIn("report | ConvertTo-Json -Depth 7",s)
        self.assertIn("backups=$summary.ToArray()",s)
        self.assertNotIn("Upload",s)
        self.assertNotIn("github.com/",s)

if __name__=="__main__": unittest.main()
