"""rpcd invokes executable providers with a single 'list' argument at discovery."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ROOT / "rebuild/veci-v2/packages"


class RpcDiscoveryTests(unittest.TestCase):
    def test_list_with_no_method_argument(self):
        providers = {
            PACKAGES / "veci-v2-runtime/veci2-status": {"status", "ethernetPorts", "capabilities", "smsProvider"},
            PACKAGES / "veci-v2-runtime/veci2-wifi": {"status", "setVisibility", "setSsid"},
            PACKAGES / "veci-v2-runtime/veci2-lte-policy": {"status", "setFailover", "setApn"},
            PACKAGES / "veci-v2-package-manager/veci2-apk": {"status", "search", "preflight", "install"},
            PACKAGES / "veci-v2-ipv6/files/usr/libexec/rpcd/veci2-ipv6": {"status", "save"},
            ROOT / "source/veci-cellular-we5927/files/usr/libexec/rpcd/veci.sms": {"getConfig", "listMessages", "sendMessage"},
        }
        for path, required in providers.items():
            with self.subTest(provider=path.name):
                reply = subprocess.run(["sh", str(path), "list"], stdin=subprocess.DEVNULL,
                                       capture_output=True, text=True, timeout=3)
                self.assertEqual(reply.returncode, 0, reply.stderr)
                methods = json.loads(reply.stdout)
                self.assertTrue(required.issubset(methods))
                self.assertTrue(all(isinstance(params, dict) for params in methods.values()))
