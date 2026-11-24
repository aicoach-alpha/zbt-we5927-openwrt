"""Exercise installed IPv6 provider sources against native libuci on the build host."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


class NativeIpv6Acceptance(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("VECI_HOST_UCI"), "native UCI executable required")
    def test_native_ipv6_provision_toggle_rollback_and_ra_profiles(self):
        subprocess.run([sys.executable, str(ROOT / "scripts/uat/test-ipv6-host.py"),
                        os.environ["VECI_HOST_UCI"]], cwd=ROOT, check=True, timeout=90)
