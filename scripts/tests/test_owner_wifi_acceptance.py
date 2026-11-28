"""Source acceptance with native UCI, isolated config and simulated wireless hardware.

Set VECI_HOST_UCI and VECI_LIBUBOX_PREFIX to the installed host tools.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "rebuild/veci-v2/packages/veci-v2-runtime"
UAT = ROOT / "scripts/uat"


class OwnerWifi(unittest.TestCase):
    def setUp(self):
        if not os.environ.get("VECI_HOST_UCI") or not os.environ.get("VECI_LIBUBOX_PREFIX"):
            self.skipTest("host UCI and libubox fixture dependencies must be supplied")
        self.uci = Path(os.environ["VECI_HOST_UCI"]).resolve(strict=True)
        self.prefix = Path(os.environ["VECI_LIBUBOX_PREFIX"]).resolve(strict=True)
        self.env = {**os.environ, "LD_LIBRARY_PATH": str(self.prefix / "lib") + ":" + os.environ.get("LD_LIBRARY_PATH", "")}

    def suite(self, script, *args):
        run = subprocess.run([sys.executable, UAT / script, self.uci, *args], env=self.env,
                             capture_output=True, text=True, timeout=90)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("PASS:", run.stdout)

    def test_primary_ap_native_uci(self):
        self.suite("test-wifi-name-host.py")

    def test_channel_survey_acl_and_auth_native_uci(self):
        self.suite("test-wifi-controls-host.py", self.prefix)

    def test_incompatible_band_and_failed_commit_preserve_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = root / "config"
            cfg.mkdir()
            (root/"delta").mkdir()
            wireless = cfg/"wireless"
            (root/"board").write_text("zbtlink,zbt-we5927\n")
            provider = root/"provider"
            provider.write_text((PKG/"veci2-wifi").read_text().replace(
                "/tmp/sysinfo/board_name", str(root/"board")).replace(
                "/usr/libexec/veci2-wifi-controls", str(PKG/"veci2-wifi-controls")))
            shim = root/"uci"
            shim.write_text(f"""#!/bin/sh
for arg do [ "$arg" != commit ] || exit 7; done
exec "{self.uci}" -c "{cfg}" -t "{root}/delta" "$@"
""")
            shim.chmod(0o700)
            filt = root/"jsonfilter"
            filt.write_text("#!/usr/bin/env python3\nimport json,sys\nprint(json.loads(sys.argv[2])[sys.argv[4][2:]])\n")
            filt.chmod(0o700)
            for name in ("wifi", "iw", "ubus"):
                path = root/name
                path.write_text(f'#!/bin/sh\ntouch "{root}/radio-called"\nexit 8\n')
                path.chmod(0o700)
            def call(method, **args):
                run = subprocess.run(["busybox", "ash", provider, "call", method],
                                     input=json.dumps(args), text=True, check=True, capture_output=True,
                                     env={**self.env, "PATH": f"{root}:" + self.env["PATH"]}, timeout=8)
                return json.loads(run.stdout)
            for band in ("5g", "6g", "2g"):
                wireless.write_text(f"config wifi-device 'radio0'\n option band '{band}'\n"
                                    "config wifi-iface 'default_radio0'\n option device 'radio0'\n"
                                    " option mode 'ap'\n option encryption 'psk2'\n option key 'existing-key'\n"
                                    " option macfilter 'allow'\n list maclist '02:00:11:22:33:44'\n")
                before = wireless.read_bytes()
                calls = {"setAuth": {"mode":"sae", "key_hex":"61"*8},
                         "setAccess": {"mode":"deny", "addresses":"02:de:ad:be:ef:00"}}
                if band != "2g":
                    calls.update({"info":{}, "survey":{}, "setChannel":{"channel":"1"},
                                  "setSsid":{"ssid_hex":"61"}, "setVisibility":{"action":"HIDE_SSID"}})
                for method, args in calls.items():
                    with self.subTest(band=band, method=method):
                        expected = "save_failed" if band == "2g" else "channel_unavailable"
                        self.assertEqual(call(method, **args), {"ok":False, "error":expected})
                        self.assertEqual(wireless.read_bytes(), before)
                        self.assertFalse((root/"radio-called").exists())
                        self.assertEqual(list((root/"delta").iterdir()), [])

    def test_privileged_actions_have_write_acl(self):
        acl = json.loads((PKG/"veci2-status-acl.json").read_text())["veci-v2-wifi"]
        self.assertEqual(set(acl["read"]["ubus"]["veci.v2.wifi"]), {"status", "info", "activationStatus"})
        self.assertEqual(set(acl["write"]["ubus"]["veci.v2.wifi"]),
                         {"setVisibility", "setSsid", "setAutoChannel", "setChannel", "survey",
                          "setAuth", "setAccess", "activateAp"})


if __name__ == "__main__":
    unittest.main()
