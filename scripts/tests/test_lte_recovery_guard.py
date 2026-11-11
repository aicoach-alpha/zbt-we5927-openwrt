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


if __name__ == "__main__":
    unittest.main()