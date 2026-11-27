"""Isolated manual reboot RPC tests. All effects redirected to temporary files."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2]/"rebuild/veci-v2/packages/veci-v2-runtime/veci2-system-admin"
BOOT = "12345678-1234-1234-1234-123456789abc"

class ManualReboot(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.d=Path(t.name)
        (self.d/"board").write_text("zbtlink,zbt-we5927\n")
        (self.d/"boot").write_text(BOOT+"\n")
        (self.d/"verify").touch()
        (self.d/"verify").chmod(0o700)
        (self.d/"jshn").write_text("""
json_init() { :; }
json_load() { [ -n "$1" ]; }
json_get_var() {
 case "$2" in confirmation) value="$CONFIRM";; boot_id) value="$EXPECTED";; *) return 1;; esac
 export "$1=$value"
}
json_add_boolean() { printf '%s=%s\\n' "$1" "$2"; }
json_add_string() { printf '%s=%s\\n' "$1" "$2"; }
json_dump() { :; }
""")
        s=SOURCE.read_text()
        for old,new in (("/tmp/sysinfo/board_name","board"),("/proc/sys/kernel/random/boot_id","boot"),("/usr/libexec/veci2-verify-image","verify"),("/var/run/veci2-restore.action.lock","restore.lock"),("/var/run/veci2-reboot-requested","requested"),("/usr/share/libubox/jshn.sh","jshn")):
            s=s.replace(old,str(self.d/new))
        (self.d/"rpc").write_text(s)
        u=self.d/"ubus"
        u.write_text('#!/bin/sh\n[ "$*" = "-t 5 call system reboot {}" ] || exit 99\nprintf "mock request\\n" >> "$CALL_LOG"\nexit "${MOCK_RC:-0}"\n')
        u.chmod(0o700)
    def run_rpc(self,method,**env):
        base=dict(PATH=str(self.d)+":"+os.environ["PATH"],CONFIRM="REBOOT_WE5927_NOW",EXPECTED=BOOT,CALL_LOG=str(self.d/"calls"))
        base.update(env)
        return subprocess.run(["sh",str(self.d/"rpc"),"call",method],input="{}",text=True,capture_output=True,timeout=5,env=dict(os.environ,**base))
    def test_confirm_stale_and_duplicate(self):
        self.assertIn("eligible=1",self.run_rpc("rebootStatus").stdout)
        self.assertIn("confirmation_required",self.run_rpc("rebootNow",CONFIRM="no").stdout)
        self.assertIn("stale_boot_identity",self.run_rpc("rebootNow",EXPECTED="stale").stdout)
        self.assertFalse((self.d/"calls").exists())
        r=self.run_rpc("rebootNow")
        self.assertIn("requested=1",r.stdout)
        self.assertIn("reboot_verified=0",r.stdout)
        self.assertIn("reboot_already_requested",self.run_rpc("rebootNow").stdout)
        self.assertEqual((self.d/"calls").read_text().splitlines(),["mock request"])
    def test_maintenance_lock_and_uncertain_result(self):
        import fcntl
        with (self.d/"verify").open("r") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.assertIn("eligible=0",self.run_rpc("rebootStatus").stdout)
            self.assertIn("maintenance_busy",self.run_rpc("rebootNow").stdout)
            self.assertFalse((self.d/"calls").exists())
        self.assertIn("reboot_request_unconfirmed",self.run_rpc("rebootNow",MOCK_RC="1").stdout)
        self.assertIn("reboot_already_requested",self.run_rpc("rebootNow").stdout)
        self.assertEqual((self.d/"calls").read_text().splitlines(),["mock request"])
