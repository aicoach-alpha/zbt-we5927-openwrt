"""Execute original VeCI SSH/HTTPS provider via BusyBox and isolated UCI fixture."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime"
UAT=ROOT/"scripts/uat/test-access-host.py"
MOCK=ROOT/"scripts/tests/fixtures/uci_access_sandbox.py"
JSHN = r'''
json_load() {
  _input="$1"
  python3 -c 'import json,sys; json.loads(sys.argv[1])' "$_input" >/dev/null
}
json_get_var() {
  result=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get(sys.argv[2],""))' "$_input" "$2") || return 1
  eval "$1=\$result"
}
json_init() { _json=''; }
json_add_boolean() { :; }
json_add_string() {
  frag=$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1])+":"+json.dumps(sys.argv[2]))' "$1" "$2")
  if [ -n "$_json" ]; then _json="$_json,$frag"; else _json="$frag"; fi
}
json_dump() { printf '{"ok":true,%s}\n' "$_json"; }
'''


class NativeAccessAcceptance(unittest.TestCase):
    def test_original_uat_with_isolated_config_and_complete_crud(self):
        with tempfile.TemporaryDirectory(prefix="veci-access-native-") as folder:
            prefix=Path(folder)
            (prefix/"bin").mkdir()
            (prefix/"lib").mkdir()
            target=prefix/"share/libubox/jshn.sh"
            target.parent.mkdir(parents=True)
            target.write_text(JSHN)
            run=subprocess.run(["python3",str(UAT),str(MOCK),str(prefix)],
                               capture_output=True,text=True,timeout=35,
                               env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"})
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
