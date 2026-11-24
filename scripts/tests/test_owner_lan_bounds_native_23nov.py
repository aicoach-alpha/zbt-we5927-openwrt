"""Execute real OpenWrt LAN subnet guard with disposable fake UCI.

No network devices, no firmware build, no router I/O.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime"
BOUNDS=(RUNTIME/"veci2-lan-bounds").read_text()
STATIC=(RUNTIME/"veci2-static-leases").read_text()
DNS=(RUNTIME/"veci2-dns").read_text()


class LanBoundsNative(unittest.TestCase):
    def invoke(self, lan, mask, candidate):
        with tempfile.TemporaryDirectory(prefix="veci-lan-subnet-") as directory:
            root=Path(directory)
            uci=root/"uci"
            uci.write_text("""#!/bin/sh
case "$*" in
  "-q get network.lan.ipaddr") printf '%s\\n' "$TEST_LAN" ;;
  "-q get network.lan.netmask") printf '%s\\n' "$TEST_MASK" ;;
  *) exit 22 ;;
esac
""")
            uci.chmod(0o700)
            cmd=' . "$1"; lan_bounds "$2" '
            return subprocess.run(
                ["busybox","ash","-c",cmd,"_",str(RUNTIME/"veci2-lan-bounds"),candidate],
                text=True,capture_output=True,timeout=4,
                env={**os.environ,"PATH":str(root)+":"+os.environ["PATH"],
                     "TEST_LAN":lan,"TEST_MASK":mask})

    def test_24_network_broadcast_and_other_subnet_rejected(self):
        for addr,good in {
            "192.168.1.2":True,"192.168.1.254":True,
            "192.168.1.0":False,"192.168.1.255":False,
            "192.168.1.1":False,"192.168.2.25":False,
        }.items():
            with self.subTest(ip=addr):
                out=self.invoke("192.168.1.1","255.255.255.0",addr)
                self.assertEqual(out.returncode==0,good,out.stderr)

    def test_cidr_and_noncontiguous_masks_fail_closed(self):
        for lan,mask,candidate,good in [
            ("10.20.30.1/24","","10.20.30.8",True),
            ("10.20.30.1/24","","10.20.31.8",False),
            ("10.20.30.1/30","","10.20.30.2",True),
            ("10.20.30.1/30","","10.20.30.3",False),
            ("10.20.30.1/31","","10.20.30.2",False),
            ("192.168.1.1","255.0.255.0","192.168.1.2",False),
            ("0.0.0.0","255.255.255.0","0.0.0.1",False),
        ]:
            with self.subTest(lan=lan,mask=mask,ip=candidate):
                out=self.invoke(lan,mask,candidate)
                self.assertEqual(out.returncode==0,good,out.stderr)

    def test_native_shared_dns_lock_and_rollback(self):
        self.assertIn("exec 9>>/var/lock/veci2-dhcp.lock",STATIC)
        self.assertIn("exec 9>>/var/lock/veci2-dhcp.lock",DNS)
        self.assertIn("lan_bounds",STATIC)
        for provider in (STATIC,DNS):
            self.assertIn("pending_dhcp_changes",provider)
            self.assertIn("flock -n 9",provider)
            self.assertIn("cp ",provider)
            self.assertNotIn("ifdown",provider)
            self.assertNotIn("wifi reload",provider)

    def test_boundary_guard_is_parsed_by_busybox(self):
        check=subprocess.run(["busybox","ash","-n",str(RUNTIME/"veci2-lan-bounds")],
                             text=True,capture_output=True,timeout=4)
        self.assertEqual(check.returncode,0,check.stderr)


if __name__=="__main__":
    unittest.main()
