"""Offline safety tests for WE5927 LTE cold boot and AT readiness.

No real modem, USB device, router network or SIM is accessed.
"""
import re
import shutil
import subprocess
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]
SOURCE = HERE / "source/we5927-lte/files/usr/sbin/we5927-lte"
HOTPLUG = HERE / "source/we5927-lte/files/etc/hotplug.d/usb/30-we5927-lte"
INIT = HERE / "source/we5927-lte/files/etc/init.d/we5927-lte"
SH = shutil.which("sh")


def function(name):
    source = SOURCE.read_text()
    pattern = rf"(?ms)^{re.escape(name)}\(\) \{{\n.*?^\}}\n"
    match = re.search(pattern, source)
    if not match:
        raise AssertionError(f"Missing function {name}")
    return match.group()


def probe(sim="+CPIN: READY", reg="+CEREG: 0,1",
          attach="+CGATT: 1", device=True, port=True, at_busy=False):
    # Only allow fixed mock response strings from the test itself.
    assert sim in {"+CPIN: READY", "+CPIN: SIM PIN", "+CPIN: SIM PUK",
                   "+CPIN: NOT READY"}
    assert reg in {"+CEREG: 0,1", "+CEREG: 0,5", "+CEREG: 0,3",
                   "+CEREG: 0,2", "+CEREG: 0,0"}
    assert attach in {"+CGATT: 1", "+CGATT: 0"}
    stubs = f"""
cfg() {{ echo usb0; }}
ip() {{ [ {int(device)} -eq 1 ]; }}
at_port() {{ [ {int(port)} -eq 1 ] && echo /dev/null; }}
at() {{
  [ {int(at_busy)} -eq 0 ] || return 1
  case "$1" in
    'AT+CPIN?') echo '{sim}' ;;
    'AT+CEREG?') echo '{reg}' ;;
    'AT+CGATT?') echo '{attach}' ;;
    *) return 1 ;;
  esac
}}
"""
    res = subprocess.run([SH, "-c", stubs + function("modem_readiness_phase") +
                          "\nmodem_readiness_phase\n"],
                         text=True, capture_output=True, timeout=4, check=True)
    return res.stdout.strip()


class TestColdbootReadiness(unittest.TestCase):
    def test_attached_sim_and_registered_operator(self):
        self.assertEqual(probe(), "packet_attached")

    def test_roaming_is_registered(self):
        self.assertEqual(probe(reg="+CEREG: 0,5"), "packet_attached")

    def test_packet_session_detached(self):
        self.assertEqual(probe(attach="+CGATT: 0"), "packet_detached")

    def test_operator_denied(self):
        self.assertEqual(probe(reg="+CEREG: 0,3"), "registration_denied")

    def test_operator_searching(self):
        self.assertEqual(probe(reg="+CEREG: 0,2"), "searching_for_operator")

    def test_operator_not_registered(self):
        self.assertEqual(probe(reg="+CEREG: 0,0"), "searching_for_operator")

    def test_sim_requires_pin_no_auto_unlock(self):
        self.assertEqual(probe(sim="+CPIN: SIM PIN"), "sim_pin_required")

    def test_sim_requires_puk_no_auto_unlock(self):
        self.assertEqual(probe(sim="+CPIN: SIM PUK"), "sim_puk_required")

    def test_sim_not_ready(self):
        self.assertEqual(probe(sim="+CPIN: NOT READY"), "sim_not_ready")

    def test_busy_at_port_yields_unknown_not_radio_reset(self):
        self.assertEqual(probe(at_busy=True), "at_busy_or_unavailable")

    def test_missing_at_port(self):
        self.assertEqual(probe(port=False), "at_unavailable")

    def test_missing_usb_interface(self):
        self.assertEqual(probe(device=False), "usb_missing")

    def test_probe_is_read_only(self):
        script = function("modem_readiness_phase")
        self.assertNotRegex(
            script, r"\b(?:ifup|ifdown|power_cycle|set_sim|soft_reconnect|"
                    r"uci|wifi|modprobe|usb_repair)\b")
        self.assertNotIn("AT+CIMI", script)
        self.assertNotIn("AT+CGSN", script)

    def test_hotplug_cannot_flap_network_or_radio(self):
        code = HOTPLUG.read_text()
        commands = "\n".join(
            l for l in code.splitlines() if not l.lstrip().startswith("#"))
        self.assertNotRegex(
            commands, r"\b(?:ifup|ifdown|wifi|power_cycle|usb_repair|"
                      r"network restart|AT\+CFUN)\b")
        self.assertIn('"$ACTION" = add', commands)
        subprocess.run([SH, "-n", str(HOTPLUG)], check=True)

    def test_lte_daemon_reload_trigger_is_narrow(self):
        source = INIT.read_text()
        self.assertIn("procd_add_reload_trigger we5927_lte\n", source)
        self.assertNotIn("procd_add_reload_trigger we5927_lte network", source)
        subprocess.run([SH, "-n", str(INIT)], check=True)

    def test_rndis_local_link_not_claimed_as_public_internet(self):
        source = function("status_fast_json")
        self.assertIn('json_add_boolean data_link_up "$data_link"', source)
        self.assertIn('json_add_boolean internet_verified "$online"', source)
        self.assertIn('json_add_string modem_phase "$modem_phase"', source)
        self.assertIn('now-sample_time', source)
        self.assertIn('runtime_stage', source)

    def test_diagnostics_stay_in_tmpfs(self):
        source = function("performance_state")
        self.assertIn("/tmp/veci-lte-performance.state", source)
        self.assertIn("modem_phase=%s", source)
        self.assertNotIn("/overlay", source)


    def test_startup_config_validation_never_mutates_network_or_firewall(self):
        source = function("ensure_network")
        commands = "\n".join(
            line for line in source.splitlines()
            if not line.lstrip().startswith("#")
        )
        self.assertNotRegex(
            commands, r"\b(?:commit|add_list|uci set|reload|ifup|ifdown|wifi)\b")
        self.assertIn("network.lte", source)

    def test_valid_lte_network_does_not_restart_anything(self):
        script = (
            "cfg() { echo usb0; }\n"
            "log() { :; }\n"
            "uci() { case \"$3\" in network.lte) echo interface;; "
            "network.lte.device) echo usb0;; network.lte.proto) echo dhcp;; "
            "*) return 1;; esac; }\n"
            + function("ensure_network")
            + "\nensure_network; echo rc=$?\n"
        )
        out = subprocess.run(
            [SH, "-c", script], capture_output=True, text=True,
            timeout=4, check=True).stdout.strip()
        self.assertEqual(out, "rc=0")

    def test_invalid_lte_protocol_fails_closed(self):
        script = (
            "cfg() { echo usb0; }\n"
            "log() { :; }\n"
            "uci() { case \"$3\" in network.lte) echo interface;; "
            "network.lte.device) echo usb0;; network.lte.proto) echo ppp;; "
            "*) return 1;; esac; }\n"
            + function("ensure_network")
            + "\nensure_network; echo rc=$?\n"
        )
        out = subprocess.run(
            [SH, "-c", script], capture_output=True, text=True,
            timeout=4, check=True).stdout.strip()
        self.assertEqual(out, "rc=1")

    def test_missing_lte_section_is_reported_not_created(self):
        script = (
            "cfg() { echo usb0; }\n"
            "log() { :; }\n"
            "uci() { return 1; }\n"
            + function("ensure_network")
            + "\nensure_network; echo rc=$?\n"
        )
        out = subprocess.run(
            [SH, "-c", script], capture_output=True, text=True,
            timeout=4, check=True).stdout.strip()
        self.assertEqual(out, "rc=1")


if __name__ == "__main__":
    unittest.main()
