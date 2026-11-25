"""Execute original VeCI SSH/HTTPS provider via BusyBox and isolated UCI fixture."""
import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime"
UAT=ROOT/"scripts/uat/test-access-host.py"
MOCK=ROOT/"scripts/tests/fixtures/uci_access_sandbox.py"
class NativeAccessAcceptance(unittest.TestCase):
    def test_original_uat_with_isolated_config_and_complete_crud(self):
        # Use actual OpenWrt host libubox instead of a Python-per-JSON-call
        # mock. The old shim launched many Python subprocesses and timed out
        # under CI/NAS load despite the source provider remaining correct.
        native_prefix=os.environ.get("VECI_LIBUBOX_PREFIX","")
        self.assertTrue(native_prefix, "native libubox is required; never skip")
        prefix=Path(native_prefix).resolve(strict=True)
        self.assertTrue((prefix/"bin/jshn").is_file())
        self.assertTrue((prefix/"share/libubox/jshn.sh").is_file())
        env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1",
             "LD_LIBRARY_PATH":str(prefix/"lib")+":"+os.environ.get("LD_LIBRARY_PATH","")}
        run=subprocess.run(["python3",str(UAT),str(MOCK),str(prefix)],
                           capture_output=True,text=True,timeout=65,env=env)
        self.assertEqual(run.returncode,0,run.stdout+"\n"+run.stderr)
        for fragment in ("SSH/HTTPS status","idle timeout","TLS redirect",
                         "stale revisions","locking","pending changes",
                         "unrelated config preservation","board and ACL"):
            self.assertIn(fragment,run.stdout)

    def test_access_rpc_writes_only_config_without_restarting_network(self):
        src=(RUNTIME/"veci2-access").read_text()
        acl=json.loads((RUNTIME/"veci2-access-acl.json").read_text())
        scoped=acl["veci-v2-access"]
        self.assertEqual(scoped["read"]["ubus"]["veci.v2.access"],["status"])
        self.assertEqual(set(scoped["write"]["ubus"]["veci.v2.access"]),{"setIdle","requireHttps"})
        for marker in ("stale_configuration","multiple_ssh_instances",
                       "pending_changes","https_unconfigured","missing_certificate"):
            self.assertIn(marker,src)
        self.assertIn("flock -n 9",src)
        for forbidden in ("wifi reload","ifdown","AT+CFUN","sysupgrade","reboot"):
            self.assertNotIn(forbidden,src)
        subprocess.run(["busybox","ash","-n",str(RUNTIME/"veci2-access")],check=True)


if __name__=="__main__":
    unittest.main()
