"""Offline tests: LTE DHCP recovery never flaps a working local gateway."""
import re
import subprocess
import shutil
import unittest
from pathlib import Path

SH = shutil.which('sh') or str(Path(r'C:\Program Files\Git\usr\bin\sh.exe'))
SOURCE = Path(__file__).parents[2] / "source/we5927-lte/files/usr/sbin/we5927-lte"


def fn(text, name):
    match = re.search(rf"(?ms)^{name}\(\) \{{\n.*?^\}}\n", text)
    assert match, name
    return match.group()


def run(target, ubus_ok=True, gateway_after=3):
    stubs = f"""
u=0; g=0; up=0; down=0
ubus() {{ u=$((u+1)); [ {int(ubus_ok)} -eq 1 ]; }}
sleep() {{ :; }}
log() {{ :; }}
ifup() {{ up=$((up+1)); }}
ifdown() {{ down=$((down+1)); }}
gateway_ok() {{ g=$((g+1)); [ "$g" -ge {gateway_after} ]; }}
"""
    body = fn(SOURCE.read_text(), target)
    script = stubs + body + f"\n{target}; rc=$?; echo rc=$rc ubus=$u gateway=$g ifup=$up ifdown=$down\n"
    result = subprocess.run([str(SH), "-c", script], text=True, capture_output=True)
    if result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout.strip()


class TestRecovery(unittest.TestCase):
    def test_failed_renew_must_not_call_ifup(self):
        self.assertEqual(run("renew_lte", False), "rc=1 ubus=1 gateway=0 ifup=0 ifdown=0")

    def test_renew_waits_for_local_gateway(self):
        self.assertEqual(run("renew_lte", True, 3), "rc=0 ubus=1 gateway=3 ifup=0 ifdown=0")

    def test_renew_timeout_does_not_flap_interface(self):
        self.assertEqual(run("renew_lte", True, 999), "rc=1 ubus=1 gateway=5 ifup=0 ifdown=0")

    def test_repair_skips_ifdown_when_link_returns(self):
        self.assertEqual(run("repair_lte_interface", True, 1), "rc=0 ubus=0 gateway=1 ifup=0 ifdown=0")

    def test_repair_only_for_persistent_local_failure(self):
        self.assertEqual(run("repair_lte_interface", True, 999), "rc=1 ubus=0 gateway=2 ifup=1 ifdown=1")



def invoke_manual(data_up, gateway_up, renew_ok, repair_ok, detached):
    script = f"""
renew_calls=0; repair_calls=0; radio_calls=0; cfun_calls=0
data_ok() {{ [ {int(data_up)} -eq 1 ]; }}
gateway_ok() {{ [ {int(gateway_up)} -eq 1 ]; }}
renew_lte() {{ renew_calls=$((renew_calls+1)); [ {int(renew_ok)} -eq 1 ]; }}
repair_lte_interface() {{ repair_calls=$((repair_calls+1)); [ {int(repair_ok)} -eq 1 ]; }}
radio_or_link_lost() {{ radio_calls=$((radio_calls+1)); [ {int(detached)} -eq 1 ]; }}
soft_reconnect() {{ cfun_calls=$((cfun_calls+1)); }}
log() {{ :; }}
""" + fn(SOURCE.read_text(), "manual_reconnect") + """
manual_reconnect; rc=$?
echo "rc=$rc renew=$renew_calls repair=$repair_calls radio=$radio_calls cfun=$cfun_calls"
"""
    result = subprocess.run([str(SH), "-c", script], text=True, capture_output=True)
    if result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout.strip()


def invoke_radio(carrier, attached, ip_exists=False):
    # Mocking the modem AT response rather than touching a real serial port.
    script = f"""
cfg() {{ echo usb0; }}
ip() {{ [ "$1" = link ] && return 0; [ {int(ip_exists)} -eq 1 ]; }}
cat() {{ echo {carrier}; }}
at_port() {{ echo /dev/null; }}
at() {{
  [ "{attached}" != busy ] || return 1
  echo '+CGATT: {attached}'
}}
""" + fn(SOURCE.read_text(), "radio_or_link_lost") + """
radio_or_link_lost; echo "radio_loss=$?"
"""
    result = subprocess.run([str(SH), "-c", script], text=True, capture_output=True)
    if result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout.strip()


class TestLowDowntimeReconnect(unittest.TestCase):
    def test_manual_reconnect_skips_healthy_internet(self):
        self.assertEqual(invoke_manual(True, False, False, False, True),
                         "rc=0 renew=0 repair=0 radio=0 cfun=0")

    def test_manual_reconnect_skips_healthy_gateway_even_if_public_ping_fails(self):
        self.assertEqual(invoke_manual(False, True, False, False, True),
                         "rc=0 renew=0 repair=0 radio=0 cfun=0")

    def test_manual_reconnect_renews_missing_local_gateway_first(self):
        self.assertEqual(invoke_manual(False, False, True, False, True),
                         "rc=0 renew=1 repair=0 radio=0 cfun=0")

    def test_manual_reconnect_repair_can_recover_without_modem_reset(self):
        self.assertEqual(invoke_manual(False, False, False, True, True),
                         "rc=0 renew=1 repair=1 radio=0 cfun=0")

    def test_manual_reconnect_does_not_cfun_attached_modem(self):
        self.assertEqual(invoke_manual(False, False, False, False, False),
                         "rc=1 renew=1 repair=1 radio=1 cfun=0")

    def test_manual_reconnect_cfun_only_with_detached_modem(self):
        self.assertEqual(invoke_manual(False, False, False, False, True),
                         "rc=0 renew=1 repair=1 radio=1 cfun=1")

    def test_missing_dhcp_ip_with_attached_modem_does_not_trigger_radio_reset(self):
        self.assertEqual(invoke_radio(1, 1, ip_exists=False), "radio_loss=1")

    def test_carrier_is_physically_down(self):
        self.assertEqual(invoke_radio(0, 1), "radio_loss=0")

    def test_modem_attached_but_at_busy_fails_closed(self):
        self.assertEqual(invoke_radio(1, 'busy'), "radio_loss=1")

    def test_detached_modem_allows_reset(self):
        self.assertEqual(invoke_radio(1, 0), "radio_loss=0")


if __name__ == "__main__":
    unittest.main()