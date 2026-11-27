"""Validate shell syntax and non-destructive contract for router MTD hash comparison."""
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"scripts/veci-we5927-compare-live-mtd-hashes-20261127.ps1"
REGISTRY=ROOT/"rebuild/veci-v2/contracts/veci-v2-bug-registry-20261126.json"

class LiveReadonlyComparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code=SCRIPT.read_text()
        m=re.search(r"(?ms)^\$script = @'\n(.*?)\n'@",cls.code)
        assert m,"literal remote shell body required"
        cls.shell=m.group(1)

    def test_remote_shell_is_valid_busybox_ash(self):
        subprocess.run(["busybox","ash","-n"],input=self.shell,text=True,check=True,timeout=7)
        for token in ('/tmp/sysinfo/board_name','/proc/mtd','sha256sum "/dev/mtd$n"',
                      'LIVE_MTD_HASHES_READ_ONLY_COMPLETE=YES'):
            self.assertIn(token,self.shell)
        for idx,size in [(0,'00030000'),(1,'00010000'),(2,'00010000'),
                         (3,'007a0000'),(7,'00010000')]:
            self.assertRegex(self.shell,rf"\^mtd{idx}:.*{size}")
        self.assertIn("StrictHostKeyChecking=yes",self.code)
        self.assertIn("root@192.168.1.1",self.code)

    def test_no_write_operations_or_false_release_acceptance(self):
        for phrase in ('mtd write','flash_erase','sysupgrade','reboot','wifi reload',
                       'uci set','uci commit','dd if=','dd of=','wget','curl',
                       'ubus call network','/dev/mtdblock'):
            self.assertNotIn(phrase,self.shell)
        self.assertNotIn("mtd write",self.code)
        self.assertIn("firmware_flash_authorized=$false",self.code)
        self.assertIn("bootloader_recovery_test='NOT_RUN'",self.code)
        self.assertIn("image_restore_format='NOT_VERIFIED'",self.code)
        self.assertIn("source_audit_file=$AuditJson",self.code)
        self.assertIn("STOP=INCOMPLETE_ROUTER_HASH_RECEIPT",self.code)

    def test_references_are_strict_and_counts_complete(self):
        self.assertIn("we5927-local-recovery-audit.v1",self.code)
        self.assertIn("HISTORICAL_SHA_PASS",self.code)
        self.assertIn("SIZE_PASS_HASH_RECORDED_NOT_ROUTER_MATCHED",self.code)
        self.assertIn("NOV23",self.code)
        self.assertIn("NOV25",self.code)
        self.assertIn("MATCH_NEITHER",self.code)
        self.assertIn("LIVE_HASH_COMPARISON_COMPLETE=YES",self.code)
        self.assertIn("remote -contains 'LIVE_MTD_HASHES_READ_ONLY_COMPLETE=YES'",self.code)

    def test_rel003_preflight_is_scoped_not_accepted_as_release(self):
        data=json.loads(REGISTRY.read_text())
        bug=next(x for x in data["bugs"] if x["id"]=="REL-003")
        self.assertEqual(bug["candidate_hardware"],"not_tested")
        self.assertEqual(bug["source_state"],"requires_hardware_verification")
        self.assertEqual(bug["candidate_preflight"]["sysupgrade_test_only"],"owner_reported_pass")
        self.assertEqual(bug["candidate_preflight"]["rollback_and_restore"],"not_verified")
        self.assertEqual(bug["candidate_preflight"]["live_new_firmware_uat"],"not_performed")

if __name__=="__main__": unittest.main()
