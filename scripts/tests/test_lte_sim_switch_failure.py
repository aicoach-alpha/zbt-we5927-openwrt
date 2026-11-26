"""SIM selector failures must stop the manual and fallback paths."""
from pathlib import Path
import subprocess
import unittest

SOURCE = (Path(__file__).resolve().parents[2] /
          "source/we5927-lte/files/usr/sbin/we5927-lte").read_text()
FUNCTIONS, DISPATCH = SOURCE.rsplit('\ncase "$1" in', 1)


def simulate(stubs, command, *args):
    safe = "network_manager_safe() { :; }\n"
    if command.startswith('case "$1" in'):
        safe += 'cfg() { [ "$1" = sim ] && echo 1; }\nselector_slot() { echo 1; }\n'
    return subprocess.run(["sh", "-c", FUNCTIONS + "\n" + safe + stubs + "\n" + command,
                           "we5927-lte", *args], capture_output=True, text=True, timeout=5)


class SimSwitchFailureTests(unittest.TestCase):
    def test_manual_selector_failure_preserves_error_and_stops(self):
        for rc in (1, 2):
            stubs = f'set_sim() {{ return {rc}; }}\ncycle_modem_power() {{ echo power; }}\napply_apn() {{ echo apn; }}\nifup() {{ echo up >&2; }}'
            result = simulate(stubs, 'case "$1" in' + DISPATCH, 'sim', '2')
            self.assertEqual(result.returncode, rc)
            self.assertEqual(result.stdout + result.stderr, '')

    def test_persistence_failure_does_not_report_success(self):
        for failing in ('set', 'commit'):
            stubs = f"""
cfg() {{ case "$1" in sim) echo 1 ;; esac; }}
gpio_set() {{ return 0; }}
uci() {{ [ "$2" = changes ] && return 0; [ "$4" != {failing} ]; }}
log() {{ :; }}
"""
            result = simulate(stubs, 'set_sim 2')
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, '')

    def test_failed_rollback_stops_before_second_cycle(self):
        for ready in ('true', 'false'):
            stubs = f"""
set_sim() {{ echo "select $1"; [ "$1" = 2 ]; }}
cycle_modem_power() {{ echo power; }}
sim_ready_at_port() {{ {ready}; }}
wait_at() {{ :; }}
apply_apn_at_ready() {{ :; }}
ifup() {{ :; }}
data_ok() {{ return 1; }}
sleep() {{ :; }}
log() {{ :; }}
"""
            result = simulate(stubs, 'auto_switch_sim 1 2')
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout.splitlines(), ['select 2', 'power', 'select 1'])

    def test_pending_configuration_leaves_gpio_untouched(self):
        stubs = """
cfg() { case "$1" in sim) echo 1 ;; esac; }
uci() { echo pending; }
gpio_set() { echo unexpected_gpio; }
log() { :; }
"""
        result = simulate(stubs, 'set_sim 2')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, '')

    def test_same_slot_with_pending_edits_preserves_hardware(self):
        stubs = """
cfg() { echo 2; }
uci() { echo pending; }
gpio_set() { echo unexpected; }
log() { :; }
"""
        result = simulate(stubs, 'set_sim 2')
        self.assertEqual((result.returncode, result.stdout), (1, ''))

    def test_selector_readback_handles_polarity_and_missing_line(self):
        stubs = """
cfg() { case "$1" in sim_gpio) echo "$pin";; sim1_value) echo "$first_cfg";; sim2_value) echo "$second_cfg";; esac; }
cat() { [ "$1" = /sys/class/gpio/sim_select/value ] && [ "$line" != missing ] && echo "$line"; }
gpio_path() { echo unexpected >&2; return 1; }
"""
        for first, second, level, pin, expected in (
            ('1', '0', '1', '46', '1'), ('1', '0', '0', '46', '2'),
            ('0', '1', '1', '46', '2'), ('0', '1', '0', '46', '1'),
            ('', '', '1', '', '1'), ('1', '1', '1', '46', ''),
            ('1', '0', 'missing', '46', ''), ('1', '0', '1', '1', ''),
        ):
            with self.subTest(first=first, second=second, level=level, pin=pin):
                result = simulate(stubs, 'first_cfg=$1; second_cfg=$2; line=$3; pin=$4; selector_slot',
                                  first, second, level, pin)
                self.assertEqual(result.stdout.strip(), expected)
                self.assertEqual(result.returncode == 0, bool(expected))
                self.assertEqual(result.stderr, '')

    def test_manual_reconnect_stops_at_failed_stage(self):
        # Manual failure now triggers one rollback/start attempt for original SIM.
        for failed, expected in (('power', ['power', 'power']),
                                 ('at', ['power', 'power']),
                                 ('apn', ['power', 'apn', 'power', 'apn']),
                                 ('ifup', ['power', 'apn', 'ifup', 'power', 'apn', 'ifup'])):
            stubs = """
set_sim() { :; }
cycle_modem_power() { echo power >&3; [ "$failed" != power ]; }
wait_at() { [ "$failed" != at ]; }
log() { :; }
apply_apn_at_ready() { echo apn >&3; [ "$failed" != apn ]; }
lte_netifd_call() { echo ifup >&3; [ "$failed" != ifup ]; }
exec 3>&1
"""
            result = simulate(stubs + 'failed=' + failed, 'case "$1" in' + DISPATCH, 'sim', '2')
            self.assertNotEqual(result.returncode, 0, failed)
            self.assertEqual(result.stdout.splitlines(), expected)

    def test_gpio_failure_stops_before_sim_reconnect(self):
        for failed, expected in (('0', ['gpio 0']), ('1', ['gpio 0', 'gpio 1'])):
            stubs = """
cfg() { :; }
log() { :; }
sleep() { :; }
usb_repair() { :; }
wait_at() { echo wait; }
lte_netifd_call() { :; }
gpio_set() { echo "gpio $2"; [ "$2" != "$failed" ]; }
"""
            result = simulate(stubs + 'failed=' + failed, 'power_cycle')
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout.splitlines(), expected)

    def test_failed_new_apn_restores_old_slot_once(self):
        stubs = """
set_sim() { slot=$1; echo "select $1"; }
cycle_modem_power() { echo "cycle $slot"; }
wait_at() { :; }
sim_ready_at_port() { :; }
apply_apn_at_ready() { echo "apn $slot"; [ "$slot" = 1 ]; }
lte_netifd_call() { echo "up $slot" >&3; }
data_ok() { echo unexpected_probe; return 0; }
log() { :; }
exec 3>&1
"""
        result = simulate(stubs, 'auto_switch_sim 1 2')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines(), ['select 2', 'cycle 2', 'apn 2',
                                                      'select 1', 'cycle 1', 'apn 1', 'up 1'])

    def test_standalone_cycle_requests_rndis_even_without_at(self):
        stubs = """
cycle_modem_power() { :; }
wait_at() { return 1; }
lte_netifd_call() { echo "$1" >&3; }
exec 3>&1
"""
        result = simulate(stubs, 'power_cycle')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines(), ['up'])

    def test_successful_trial_checks_data_after_starting_new_slot(self):
        stubs = """
set_sim() { echo "select $1"; }
cycle_modem_power() { echo power; }
wait_at() { echo at; }
sim_ready_at_port() { echo ready; }
apply_apn_at_ready() { echo apn; }
lte_netifd_call() { echo "up lte" >&3; }
data_ok() { echo probe; }
log() { :; }
exec 3>&1
"""
        result = simulate(stubs, 'auto_switch_sim 1 2')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines(),
                         ['select 2', 'power', 'at', 'ready', 'apn', 'up lte', 'probe'])

    def test_manual_success_runs_expected_reconnect_steps(self):
        stubs = """
set_sim() { echo "select $1"; }
cycle_modem_power() { echo power; }
wait_at() { :; }
apply_apn_at_ready() { echo apn; }
lte_netifd_call() { :; }
"""
        result = simulate(stubs, 'case "$1" in' + DISPATCH, 'sim', '2')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines(), ['select 2', 'power', 'apn'])
