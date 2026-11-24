"""Run the existing WE2825 Ethernet WAN/LAN RPC implementation with native UCI.

Source acceptance only: no live network, no physical router, no firmware build.
"""
from pathlib import Path
import json
import os
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
PACKAGES=ROOT/"rebuild/veci-v2/packages"
RUNTIME=PACKAGES/"veci-v2-runtime"
UI=PACKAGES/"veci-v2-ui"

class ExistingNativeInterfacesAcceptance(unittest.TestCase):
    def test_existing_wan_lan_rpc_native_uci_and_preserves_lte_ipv6(self):
        host_uci=os.getenv("VECI_HOST_UCI")
        prefix=os.getenv("VECI_LIBUBOX_PREFIX")
        self.assertTrue(host_uci and prefix,"native UCI and libubox must be supplied; never silently skip")
        lib=Path(prefix)/"share/libubox/jshn.sh"
        self.assertTrue(Path(host_uci).is_file())
        self.assertTrue(lib.is_file())
        env={**os.environ,
             "PATH":str(Path(prefix)/"bin")+":"+os.environ.get("PATH",""),
             "LD_LIBRARY_PATH":str(Path(prefix)/"lib")+":"+os.environ.get("LD_LIBRARY_PATH","")}
        command=[sys.executable,str(ROOT/"scripts/uat/test-interfaces-host.py"),host_uci,str(lib)]
        result=subprocess.run(command,cwd=ROOT,env=env,text=True,capture_output=True,timeout=90)
        self.assertEqual(result.returncode,0,result.stdout+"\n"+result.stderr)
        for expected in ("PASS LAN IPv4","DHCP/static WAN","overlap and gateway rejection",
                         "stale revision","LTE/IPv6/device/metric preservation"):
            self.assertIn(expected,result.stdout)

    def test_native_ui_rpc_acl_and_installation(self):
        runtime_make=(RUNTIME/"Makefile").read_text()
        ui_make=(UI/"Makefile").read_text()
        self.assertIn("veci2-interfaces $(1)/usr/libexec/rpcd/veci.v2.interfaces",runtime_make)
        self.assertIn("veci2-interfaces-acl.json",runtime_make)
        self.assertIn("interfaces.js",ui_make)
        acl=json.loads((RUNTIME/"veci2-interfaces-acl.json").read_text())["veci-v2-interfaces"]
        self.assertEqual(acl["read"]["ubus"]["veci.v2.interfaces"],["status"])
        self.assertEqual(acl["write"]["ubus"]["veci.v2.interfaces"],["save"])
        html=(UI/"files/www/veci2/index.html").read_text()
        self.assertEqual(html.count('id="interface-form"'),1)
        self.assertIn("/veci2/interfaces.js",html)
        script=(UI/"files/www/veci2/interfaces.js").read_text()
        self.assertIn("SAVE_NETWORK",script)
        self.assertIn("revision",script)
        self.assertIn("veci.v2.interfaces",script)
        subprocess.run(["node","--check",str(UI/"files/www/veci2/interfaces.js")],check=True,capture_output=True,timeout=8)
        subprocess.run(["busybox","ash","-n",str(RUNTIME/"veci2-interfaces")],check=True,capture_output=True,timeout=8)

if __name__=="__main__":
    unittest.main()
