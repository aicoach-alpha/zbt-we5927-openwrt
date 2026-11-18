"""SIM selector failures must stop the manual and fallback paths."""
from pathlib import Path
import subprocess
import unittest

SOURCE = (Path(__file__).resolve().parents[2] /
          "source/we5927-lte/files/usr/sbin/we5927-lte").read_text()
FUNCTIONS, DISPATCH = SOURCE.rsplit('\ncase "$1" in', 1)


def simulate(stubs, command, *args):
    return subprocess.run(["sh", "-c", FUNCTIONS + "\n" + stubs + "\n" + command,
                           "we5927-lte", *args], capture_output=True, text=True, timeout=5)


class SimSwitchFailureTests(unittest.TestCase):
    def test_manual_selector_failure_preserves_error_and_stops(self):
        for rc in (1, 2):
            stubs = f'set_sim() {{ return {rc}; }}\npower_cycle() {{ echo power; }}\napply_apn() {{ echo apn; }}\nifup() {{ echo up >&2; }}'
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
power_cycle() {{ echo power; }}
sim_ready() {{ {ready}; }}
apply_apn() {{ :; }}
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

    def test_manual_success_runs_expected_reconnect_steps(self):
        stubs = """
set_sim() { echo "select $1"; }
power_cycle() { echo power; }
apply_apn() { echo apn; }
ifup() { :; }
"""
        result = simulate(stubs, 'case "$1" in' + DISPATCH, 'sim', '2')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines(), ['select 2', 'power', 'apn'])
