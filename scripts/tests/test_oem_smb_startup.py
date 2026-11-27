"""Isolated native SMB startup controls; no actual init service invocation."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

R=Path(__file__).resolve().parents[2]/"rebuild/veci-v2/packages/veci-v2-runtime"

class SmbStartup(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.d=Path(t.name)
        (self.d/"board").write_text("zbtlink,zbt-we5927\n")
        (self.d/"init.d").mkdir()
        (self.d/"jshn").write_text("""
json_load() { [ -n "$1" ]; }
json_get_var() {
 case "$2" in revision) v="$REVISION";; confirmation) v="$CONFIRM";; service) v="$SERVICE";; *) return 1;; esac
 export "$1=$v"
}
json_init() { :; }
json_add_boolean() { printf '%s=%s\\n' "$1" "$2"; }
json_add_string() { printf '%s=%s\\n' "$1" "$2"; }
json_dump() { :; }
""")
        s=(R/"veci2-addon").read_text()
        for a,b in (("/tmp/sysinfo/board_name","board"),("/usr/share/libubox/jshn.sh","jshn"),("/usr/libexec/veci2-addon-profiles","profiles")):
            s=s.replace(a,str(self.d/b))
        (self.d/"rpc").write_text(s)
        s=(R/"veci2-addon-profiles").read_text().replace("/etc/init.d/",str(self.d/"init.d")+"/").replace("/var/lock/veci2-optional-services.lock",str(self.d/"lock"))
        (self.d/"profiles").write_text(s)
    def install(self,name):
        p=self.d/"init.d"/name
        p.write_text("""#!/bin/sh
case "$1" in
 enabled) [ -f "$STATE" ];;
 disable) printf '%s\\n' disable >> "$CALLS"; [ "${FAIL_DISABLE:-0}" = 0 ] || exit 1; rm -f "$STATE";;
 *) exit 99;;
esac
""")
        p.chmod(0o700)
        (self.d/"enabled").touch()
    def rpc(self,method,**env):
        args=dict(STATE=str(self.d/"enabled"),CALLS=str(self.d/"calls"),SERVICE="samba4",REVISION="",CONFIRM="DISABLE_SMB_NEXT_BOOT")
        args.update(env)
        return subprocess.run(["sh",str(self.d/"rpc"),"call",method],input="{}",text=True,capture_output=True,timeout=5,env=dict(os.environ,**args))
    def revision(self):
        return next(x.split("=",1)[1] for x in self.rpc("smbStatus").stdout.splitlines() if x.startswith("revision="))
    def test_status_absent_and_ambiguous(self):
        self.assertIn("state=absent",self.rpc("smbStatus").stdout)
        self.install("samba4")
        self.install("ksmbd")
        self.assertIn("state=ambiguous",self.rpc("smbStatus").stdout)
        self.assertIn("service_unavailable",self.rpc("disableSmbStartup").stdout)
        self.assertFalse((self.d/"calls").exists())
    def test_disable_only_and_revision(self):
        for name in ("samba4","ksmbd"):
            self.install(name)
            rev=self.revision()
            for patch,error in (({"REVISION":"stale"},"stale_configuration"),({"CONFIRM":"ENABLE"},"confirmation_required"),({"SERVICE":"other"},"stale_configuration")):
                args=dict(REVISION=rev,SERVICE=name)
                args.update(patch)
                self.assertIn(error,self.rpc("disableSmbStartup",**args).stdout)
                self.assertTrue((self.d/"enabled").exists())
            r=self.rpc("disableSmbStartup",REVISION=rev,SERVICE=name)
            self.assertIn("state=disabled",r.stdout,r.stderr)
            self.assertFalse((self.d/"enabled").exists())
            self.assertIn("stale_configuration",self.rpc("disableSmbStartup",REVISION=rev,SERVICE=name).stdout)
            (self.d/"init.d"/name).unlink()
        self.assertEqual((self.d/"calls").read_text().splitlines(),["disable","disable"])
    def test_failed_disable(self):
        self.install("samba4")
        self.assertIn("startup_disable_failed",self.rpc("disableSmbStartup",REVISION=self.revision(),FAIL_DISABLE="1").stdout)
        self.assertTrue((self.d/"enabled").exists())
