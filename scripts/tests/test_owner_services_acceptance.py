"""Execute original boot-service provider against a disposable init.d/rc.d tree."""
from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "rebuild/veci-v2/packages/veci-v2-runtime"
HOST_TEST = ROOT / "scripts/uat/test-services-host.py"

# Small test-only jshn adapter for CI without libubox. On andre-nas, the
# separate original UAT also runs against its real native libubox/jshn.
JSHN_FIXTURE = r'''
json_load() {
  _json_input="$1"
  python3 -c 'import json,sys; json.loads(sys.argv[1])' "$_json_input" >/dev/null
}
json_get_var() {
  value=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get(sys.argv[2],""))' "$_json_input" "$2") || return 1
  eval "$1=\$value"
}
json_init() { _json_rows=''; _json_ok='0'; }
json_add_array() { :; }
json_add_object() { _json_name='';_json_enabled='0';_json_mutable='0'; }
json_add_string() { [ "$1" != 'name' ] || _json_name="$2"; }
json_add_boolean() {
  case "$1" in
    ok) _json_ok="$2" ;;
    enabled) _json_enabled="$2" ;;
    mutable) _json_mutable="$2" ;;
  esac
}
json_close_object() {
  a=false;b=false
  [ "$_json_enabled" != 1 ] || a=true
  [ "$_json_mutable" != 1 ] || b=true
  item='{"name":"'"$_json_name"'","enabled":'"$a"',"mutable":'"$b"'}'
  if [ -n "$_json_rows" ]; then _json_rows="$_json_rows,$item"; else _json_rows="$item"; fi
}
json_close_array() { :; }
json_dump() { printf '{"ok":true,"services":[%s]}\n' "$_json_rows"; }
'''


class NativeServiceAcceptance(unittest.TestCase):
    def test_real_provider_lifecycle_in_sandbox(self):
        with tempfile.TemporaryDirectory(prefix="veci-services-accept-") as directory:
            prefix = Path(directory)
            script = prefix / "share/libubox/jshn.sh"
            script.parent.mkdir(parents=True)
            script.write_text(JSHN_FIXTURE)
            (prefix / "bin").mkdir()
            (prefix / "lib").mkdir()
            result = subprocess.run(["python3",str(HOST_TEST),str(prefix)],
                env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"},text=True,
                capture_output=True,timeout=28)
            self.assertEqual(result.returncode,0,result.stdout+"\n"+result.stderr)
            for expected in ("startup inventory", "enable/disable", "stale selection",
                             "lock", "network/LTE protection", "failed write",
                             "symlink rejection", "exact board", "ACL"):
                self.assertIn(expected,result.stdout)

    def test_no_unrestricted_lte_network_or_ssh_boot_changes(self):
        src = (RUNTIME / "veci2-services").read_text()
        acl = json.loads((RUNTIME/"veci2-services-acl.json").read_text())
        scoped = acl["veci-v2-services"]
        self.assertEqual(scoped["read"]["ubus"]["veci.v2.services"],["status"])
        self.assertEqual(scoped["write"]["ubus"]["veci.v2.services"],["save"])
        self.assertIn('cron|sysntpd',src)
        self.assertIn("protected_service",src)
        self.assertIn("stale_selection",src)
        self.assertIn("init_unavailable",src)
        self.assertNotIn("ifdown",src)
        self.assertNotIn("AT+CFUN",src)
        subprocess.run(["busybox","ash","-n",str(RUNTIME/"veci2-services")],check=True)


if __name__ == "__main__":
    unittest.main()
