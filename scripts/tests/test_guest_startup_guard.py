"""VeCI guest provisioning offline safety regression tests.
No router, Wi-Fi, or network services are started by these tests.
"""
import re
import shutil
import subprocess
import unittest
from pathlib import Path

SOURCE = Path(__file__).parents[2] / "source/veci-guest/veci.app.guest"
SH = shutil.which("sh") or r"C:\Program Files\Git\usr\bin\sh.exe"

def fun(name):
    src=SOURCE.read_text(encoding="utf-8")
    match=re.search(rf"(?ms)^{name}\(\) \{{\n.*?^\}}\n",src)
    if match is None:raise AssertionError(f"missing {name}")
    return match.group()

def run_shell(func, prefix, suffix):
    result=subprocess.run([str(SH),"-c",prefix+"\n"+fun(func)+"\n"+suffix],
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=12)
    if result.returncode:raise AssertionError(result.stderr)
    return result.stdout.strip()

class GuestSafety(unittest.TestCase):
    def test_provision_does_not_restart_wifi_network(self):
        mock="""wifi_calls=0; service_calls=0; discards=0; rollbacks=0
portal_snapshot_begin(){ return 0; }
provision_base(){ return 0; }
portal_snapshot_discard(){ discards=$((discards+1)); }
portal_snapshot_restore(){ rollbacks=$((rollbacks+1)); }
wifi(){ wifi_calls=$((wifi_calls+1)); }
service_restart(){ service_calls=$((service_calls+1)); }
"""
        out=run_shell("provision_portal",mock,"provision_portal; echo wifi=$wifi_calls service=$service_calls discard=$discards rollback=$rollbacks")
        self.assertEqual(out,"wifi=0 service=0 discard=1 rollback=0")

    def test_failed_provision_rolls_back_without_wifi_reload(self):
        mock="""wifi_calls=0; service_calls=0; discards=0; rollbacks=0
portal_snapshot_begin(){ return 0; }
provision_base(){ return 1; }
portal_snapshot_discard(){ discards=$((discards+1)); }
portal_snapshot_restore(){ rollbacks=$((rollbacks+1)); return 0; }
wifi(){ wifi_calls=$((wifi_calls+1)); }
service_restart(){ service_calls=$((service_calls+1)); }
"""
        out=run_shell("provision_portal",mock,"provision_portal; rc=$?; echo rc=$rc wifi=$wifi_calls service=$service_calls rollback=$rollbacks")
        self.assertEqual(out,"rc=1 wifi=0 service=0 rollback=1")

    def _disable(self, guest_disabled):
        mock=f"""wifi_calls=0; service_calls=0
uci(){{
  case "$*" in
    *"get wireless.veci_guest.disabled"*) echo '{guest_disabled}';;
    *"get wireless.veci_guest"*) echo wifi-iface;;
    *"get veci_guest.main.original_listen_http"*) return 1;;
    *) return 0;;
  esac
}}
service_restart(){{ service_calls=$((service_calls+1)); }}
wifi(){{ wifi_calls=$((wifi_calls+1)); }}
"""
        return run_shell("disable_portal",mock,"disable_portal; rc=$?; echo rc=$rc wifi=$wifi_calls service=$service_calls")

    def test_repeated_disable_does_not_reload_wifi(self):
        self.assertEqual(self._disable(1),"rc=0 wifi=0 service=2")

    def test_disable_active_guest_reload_wifi_once(self):
        self.assertEqual(self._disable(0),"rc=0 wifi=1 service=2")

    def test_status_reports_active_only_if_radio_and_http_are_enabled(self):
        status=fun("method_status")
        self.assertIn('get wireless.veci_guest.disabled',status)
        self.assertIn('get uhttpd.veci_guest.enabled',status)
        self.assertIn('get uspot.veci_guest',status)

    def test_rollback_has_conditional_radio_reload(self):
        rollback=fun("portal_snapshot_restore")
        self.assertIn("wifi_reload_needed=0",rollback)
        self.assertIn('if [ "$wifi_reload_needed" =',rollback)

    def test_disabled_guest_save_does_not_always_reload_wifi(self):
        saving=fun("method_save")
        self.assertIn('get wireless.veci_guest.disabled',saving)
        self.assertIn("Editing a disabled guest SSID is UCI-only",saving)

    def test_rollback_restarts_services_only_after_runtime_activation(self):
        rollback=fun("portal_snapshot_restore")
        self.assertIn('if [ "$GUEST_SERVICES_RECONFIGURED" =',rollback)
        snapshot=fun("portal_snapshot_begin")
        self.assertIn('GUEST_SERVICES_RECONFIGURED=0',snapshot)

    def test_inactive_guest_cleanup_does_not_restart_network(self):
        cleanup=fun("method_cleanup")
        self.assertIn('guest_was_active',cleanup)
        self.assertIn('Removing an inactive guest must not flap LAN/LTE DHCP',cleanup)

if __name__=="__main__":unittest.main()