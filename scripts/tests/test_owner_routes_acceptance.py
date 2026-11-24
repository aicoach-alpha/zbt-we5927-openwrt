"""Source acceptance for static routes and source-based IPv4 policy rules.

Set VECI_HOST_UCI to the native OpenWrt uci executable and VECI_LIBUBOX_PREFIX
to the installed native libubox prefix (bin/jshn, share/libubox/jshn.sh, lib).
On andre-nas, fall back to its existing test UCI and VeCI host tools prefix.
Missing host tools fail acceptance.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ROOT / "rebuild/veci-v2/packages"
RUNTIME = PACKAGES / "veci-v2-runtime"
UI = PACKAGES / "veci-v2-ui"


class NativeRoutingAcceptance(unittest.TestCase):
    def test_real_rpc_route_and_policy_crud_and_transaction_failure(self):
        env = os.environ.copy()
        prefix = Path(env.get("VECI_LIBUBOX_PREFIX") or "/missing-native-libubox")
        uci = Path(env.get("VECI_HOST_UCI") or "/missing-native-uci")
        jshn = prefix / "share/libubox/jshn.sh"
        if not shutil.which("busybox"):
            if "VECI_HOST_UCI" in env or "VECI_LIBUBOX_PREFIX" in env:
                self.fail("Explicit native UCI test toolchain requires BusyBox ash")
            self.skipTest("Native OpenWrt host integration unavailable: BusyBox ash missing; not hardware UAT")
        for tool in (uci, prefix / "bin/jshn", jshn):
            if not tool.is_file():
                if "VECI_HOST_UCI" in env or "VECI_LIBUBOX_PREFIX" in env:
                    self.fail(f"Native UCI toolchain explicitly configured but missing {tool}")
                self.skipTest(f"Native UCI fixture unavailable ({tool.name}); not hardware UAT")
        env["PATH"] = str(prefix / "bin") + os.pathsep + env["PATH"]
        env["LD_LIBRARY_PATH"] = os.pathsep.join(filter(None, [str(prefix / "lib"), env.get("LD_LIBRARY_PATH")]))
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/uat/test-routes-host.py"), str(uci), str(jshn)],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=60, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("failed commit preserves config bytes", result.stdout)

    def test_native_route_form_rpc_installation_and_least_privilege_acl(self):
        install = (RUNTIME / "Makefile").read_text()
        self.assertIn("./veci2-routes $(1)/usr/libexec/rpcd/veci.v2.routes", install)
        self.assertIn("./veci2-routes-acl.json $(1)/usr/share/rpcd/acl.d/veci-v2-routes.json", install)
        acl = json.loads((RUNTIME / "veci2-routes-acl.json").read_text())["veci-v2-routes"]
        self.assertEqual(acl["read"], {"ubus": {"veci.v2.routes": ["status"]}})
        self.assertEqual(acl["write"], {"ubus": {"veci.v2.routes": ["save", "remove"]}})
        self.assertIn("./files/www/veci2/routes.js $(1)/www/veci2/routes.js", (UI / "Makefile").read_text())
        index = (UI / "files/www/veci2/index.html").read_text()
        self.assertIn('id="route-form"', index)
        self.assertIn('src="/veci2/routes.js"', index)
        self.assertIn("rpc('veci.v2.routes'", (UI / "files/www/veci2/routes.js").read_text())
