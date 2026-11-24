"""Regression: repeated outage must not repeatedly flap the real LTE route."""
import re
from pathlib import Path
import subprocess
import unittest

SOURCE = Path(__file__).resolve().parents[2] / "source/we5927-lte/files/usr/sbin/we5927-lte"


def function(name):
    text = SOURCE.read_text()
    match = re.search(rf"(?ms)^{name}\(\) \{{\n.*?^\}}\n", text)
    assert match, name
    return match.group()


def shell_run(stubs, name, code):
    text = stubs + function(name) + code
    p = subprocess.run(["sh", "-c", text], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()


class LteCooldownTests(unittest.TestCase):
    def test_renew_only_once_in_two_minutes(self):
        stubs = """
now=1000; last_renew_attempt=0; renewed=0
date() { echo "$now"; }
log() { :; }
sleep() { :; }
ubus() { renewed=$((renewed+1)); return 0; }
gateway_ok() { return 1; }
"""
        code = """
renew_lte; first=$?
renew_lte; cooldown=$?
now=1120; renew_lte; after=$?
echo "first=$first cooldown=$cooldown after=$after renews=$renewed"
"""
        self.assertEqual(
            shell_run(stubs, "renew_lte", code),
            "first=1 cooldown=3 after=1 renews=2",
        )

    def test_interface_teardown_at_most_once_in_five_minutes(self):
        stubs = """
now=1000; last_repair_attempt=0; down=0; up=0
date() { echo "$now"; }
log() { :; }
sleep() { :; }
gateway_ok() { return 1; }
lte_netifd_call() { case "$1" in down) down=$((down+1));; up) up=$((up+1));; esac; }
lan_bridge_present() { :; }
"""
        code = """
repair_lte_interface; first=$?
repair_lte_interface; cooldown=$?
now=1300; repair_lte_interface; after=$?
echo "first=$first cooldown=$cooldown after=$after ifdown=$down ifup=$up"
"""
        self.assertEqual(
            shell_run(stubs, "repair_lte_interface", code),
            "first=1 cooldown=3 after=1 ifdown=2 ifup=2",
        )

    def test_daemon_has_explicit_cooldown_branch_before_escalating_radio(self):
        source = function("daemon")
        self.assertIn("if [ \"$renew_rc\" -eq 3 ]; then", source)
        self.assertIn("stage=dhcp_cooldown", source)
        self.assertIn("if [ \"$repair_rc\" -eq 3 ]; then", source)
        self.assertIn("stage=interface_cooldown", source)
        # Escalation is nested behind the non-cooldown repair failure branch.
        marker = source.index('stage=interface_cooldown')
        radio = source.index('stage=modem_soft_reconnect')
        self.assertLess(marker, radio)

    def daemon_harness(self, renew_exit, repair_exit):
        stubs = """
calls=0
enabled() { calls=$((calls+1)); [ "$calls" -le 3 ]; }
cfg() { [ "$1" = sim ] && echo 1 || echo 0; }
clamped_number() { echo 2; }
data_ok() { return 1; }
gateway_ok() { return 1; }
ensure_network() { :; }
power_on() { :; }
set_sim() { :; }
usb_repair() { :; }
wait_at() { :; }
sim_ready() { :; }
apply_apn_at_ready() { :; }
lte_netifd_call() { :; }
network_manager_safe() { :; }
modem_readiness_phase() { echo at_busy_or_unavailable; }
log() { :; }
sleep() { :; }
wan_diag_event() { :; }
performance_state() { echo "STATE:$stage"; }
radio_or_link_lost() { echo RADIO_RESET_CONSIDERED; return 0; }
power_cycle() { echo PHYSICAL_MODEM_RESET; }
soft_reconnect() { echo MODEM_CFUN_RESET; }
renew_lte() { echo DHCP_RENEW; return RENEW_EXIT; }
repair_lte_interface() { echo LTE_IFDOWN; return REPAIR_EXIT; }
"""
        stubs=stubs.replace("RENEW_EXIT",str(renew_exit)).replace(
            "REPAIR_EXIT",str(repair_exit))
        return shell_run(stubs,"daemon","\ndaemon\necho ENDED\n")

    def test_daemon_cooldown_renew_does_not_reenter_ifdown_or_reset(self):
        result=self.daemon_harness(3,1)
        self.assertIn("STATE:dhcp_cooldown",result)
        self.assertNotIn("LTE_IFDOWN",result)
        self.assertNotIn("MODEM_CFUN_RESET",result)
        self.assertNotIn("PHYSICAL_MODEM_RESET",result)

    def test_daemon_cooldown_teardown_does_not_escalate(self):
        result=self.daemon_harness(1,3)
        self.assertIn("STATE:interface_cooldown",result)
        self.assertIn("LTE_IFDOWN",result)
        self.assertNotIn("MODEM_CFUN_RESET",result)
        self.assertNotIn("PHYSICAL_MODEM_RESET",result)

    def test_same_script_staged_into_both_lte_sources(self):
        mirror = Path(__file__).resolve().parents[2] / "files/usr/sbin/we5927-lte"
        self.assertEqual(SOURCE.read_bytes(), mirror.read_bytes())


if __name__=="__main__":
    unittest.main()
