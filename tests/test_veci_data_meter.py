"""Synthetic no-modem tests for VeCI optional LTE data meter."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"source/veci-data-meter/files/usr/libexec/rpcd/veci.meter"
class Meter(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        root=Path(self.t.name)
        self.root=root
        self.state=root/"state/baseline.json"
        self.net=root/"sys/class/net/usb0"
        (self.net/"statistics").mkdir(parents=True)
        self.boot=root/"boot_id"
        self.boot.write_text("12345678-1234-1234-1234-123456789abc\n")
        self.set_bytes(1000000,250000)
        (self.net/"ifindex").write_text("9\n")
        self.helper=root/"jsonfilter.py"
        self.helper.write_text("""import json,sys
arg=sys.argv
path=arg[arg.index('-i')+1] if '-i' in arg else None
obj=json.load(open(path)) if path else json.load(sys.stdin)
key=arg[arg.index('-e')+1].removeprefix('@.')
val=obj.get(key)
if val is None: sys.exit(1)
print(val if not isinstance(val,bool) else str(val).lower())
""")
        source=SOURCE.read_text()
        source=source.replace("STATE=/etc/veci-data-meter/baseline.json",f"STATE={self.state}")
        source=source.replace("DIR=/etc/veci-data-meter",f"DIR={self.state.parent}")
        source=source.replace("/sys/class/net/usb0",str(self.net))
        source=source.replace("/proc/sys/kernel/random/boot_id",str(self.boot))
        source=source.replace('jsonfilter ',f'python3 {self.helper} ')
        source=source.replace('free="$(df -k /overlay | awk \'NR==2{print $4}\')"','free=65536')
        self.executable=root/"meter.sh"
        self.executable.write_text(source)
    def set_bytes(self,rx,tx):
        (self.net/"statistics/rx_bytes").write_text(str(rx))
        (self.net/"statistics/tx_bytes").write_text(str(tx))
    def invoke(self,method,data=None):
        p=subprocess.run(["sh",str(self.executable),"call",method],
            input=json.dumps(data) if data is not None else None,
            text=True,capture_output=True,timeout=4)
        self.assertEqual(p.returncode,0,p.stderr)
        return json.loads(p.stdout)
    def test_rpcd_exec_list_one_argument(self):
        # rpcd registration invokes the file with ONLY 'list'.
        p = subprocess.run(["sh",str(self.executable),"list"],
            capture_output=True,text=True,timeout=2)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stderr, "")
        declared = json.loads(p.stdout)
        self.assertEqual(declared["status"], {})
        self.assertEqual(declared["setBaseline"], {"remaining_mb":"int"})
    def test_rpcd_exec_unknown_one_argument(self):
        p = subprocess.run(["sh",str(self.executable),"unknown"],
            capture_output=True,text=True,timeout=2)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(json.loads(p.stdout)["reason"], "unknown_method")

    def test_empty_status_never_claims_balance(self):
        o=self.invoke("status")
        self.assertEqual(o["state"],"needs_baseline")
        self.assertFalse(o["carrier_authenticated"])
        self.assertIsNone(o["estimated_remaining_bytes"])
        self.assertFalse(self.state.exists(),"read-only must not persist")
    def test_explicit_manual_estimate(self):
        a=self.invoke("setBaseline",{"remaining_mb":1000})
        self.assertTrue(a["ok"])
        self.assertFalse(a["carrier_authenticated"])
        self.assertEqual(self.state.stat().st_mode & 0o777,0o600)
        self.set_bytes(1500000,500000)
        o=self.invoke("status")
        self.assertEqual(o["state"],"estimated")
        self.assertEqual(o["traffic_since_baseline_bytes"],750000)
        self.assertEqual(o["estimated_remaining_bytes"],999250000)
        self.assertNotEqual(o["source"],"carrier_authenticated")
    def test_boot_or_interface_change_invalidates(self):
        self.invoke("setBaseline",{"remaining_mb":200})
        self.boot.write_text("98765432-1234-1234-1234-123456789abc")
        self.assertEqual(self.invoke("status")["state"],"baseline_expired")
    def test_counter_rollbacks_invalidate(self):
        self.invoke("setBaseline",{"remaining_mb":200})
        self.set_bytes(500,100)
        self.assertEqual(self.invoke("status")["state"],"baseline_expired")
    def test_bad_amount_rejected_without_state(self):
        for n in (0,-1,1048577,"oops"):
            r=self.invoke("setBaseline",{"remaining_mb":n})
            self.assertEqual(r["ok"],False)
            self.assertFalse(self.state.exists())
    def test_usable_without_any_carrier_keys(self):
        text=SOURCE.read_text()
        for prohibited in ("AT+CUSD", "AT+CMGS", "/dev/ttyUSB2",
           "api.myxl", "requestOtp", "submitOtp", "token",
           "carrier_authenticated\":true", "/luci-static/"):
            self.assertNotIn(prohibited,text)
if __name__=="__main__": unittest.main()
