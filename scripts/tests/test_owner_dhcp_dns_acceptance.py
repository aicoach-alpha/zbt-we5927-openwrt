"""Reuse already-shipped native DNS and DHCP reservation host integration test."""
from pathlib import Path
import json,os,subprocess,sys,unittest

ROOT=Path(__file__).resolve().parents[2]
PKG=ROOT/"rebuild/veci-v2/packages"
RUNTIME=PKG/"veci-v2-runtime"
UI=PKG/"veci-v2-ui"

class ExistingDnsDhcpIntegration(unittest.TestCase):
    def test_existing_dns_dhcp_native_uci_lock_and_rollback(self):
        uci=os.environ.get("VECI_HOST_UCI")
        prefix=os.environ.get("VECI_LIBUBOX_PREFIX")
        self.assertTrue(uci and prefix,"native UCI/libubox required; do not skip")
        self.assertTrue(Path(uci).is_file() and (Path(prefix)/"bin/jshn").is_file())
        run=subprocess.run(
            [sys.executable,str(ROOT/"scripts/uat/test-owner-dhcp-dns.py"),uci,prefix],
            cwd=ROOT,
            env={**os.environ,
                 "PATH":str(Path(prefix)/"bin")+":"+os.environ.get("PATH",""),
                 "LD_LIBRARY_PATH":str(Path(prefix)/"lib")+":"+os.environ.get("LD_LIBRARY_PATH","")},
            text=True,capture_output=True,timeout=90)
        self.assertEqual(run.returncode,0,run.stdout+"\n"+run.stderr)
        for mark in ("PASS native UCI/BusyBox","DNS AUTO/CUSTOM","DHCP reservations",
                     "shared locking","byte-exact rollback"):
            self.assertIn(mark,run.stdout)

    def test_existing_native_rpc_gui_acl_and_no_lte_mutations(self):
        install=(RUNTIME/"Makefile").read_text()
        for name in ("dns","static-leases"):
            self.assertIn("veci2-"+name+" $(1)/usr/libexec/rpcd/",install)
            shell=(RUNTIME/("veci2-"+name)).read_text()
            self.assertIn("veci2-dhcp.lock",shell)
            for unsafe in ("ifdown","ifup","wifi reload","AT+CFUN","sysupgrade"):
                self.assertNotIn(unsafe,shell)
            subprocess.run(["busybox","ash","-n",str(RUNTIME/("veci2-"+name))],check=True,capture_output=True,timeout=8)
        acl=json.loads((RUNTIME/"veci2-status-acl.json").read_text())
        self.assertEqual(acl["veci-v2-dns"]["write"]["ubus"]["veci.v2.dns"],["set"])
        self.assertIn("dns-settings.js",(UI/"Makefile").read_text())
        self.assertIn('id="owner-lease-form"',(UI/"files/www/veci2/index.html").read_text())

if __name__=="__main__":
    unittest.main()
