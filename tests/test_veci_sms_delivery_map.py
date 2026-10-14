"""Offline v1.6.1 correlated Delivery Report tests; no modem, SMS or personal data."""
import fcntl
import json
import pathlib
import subprocess
import tempfile
import time
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/veci-sms-delivery-v161-staged/veci-sms-delivery-map"
PDU="0021000B912143658709F1000005C82293F904"
OTHER="0021000B912143658709F1000003C14021"

class DeliveryMap(unittest.TestCase):
    def setUp(self):
        self.context=tempfile.TemporaryDirectory()
        d=pathlib.Path(self.context.name)
        self.store=d/"map"
        self.lock=d/"lock"
        self.store.write_text("")
        (d/"feature").write_text("1")
        (d/"board").write_text("zbtlink,zbt-we5927")
        code=SCRIPT.read_text()
        code=code.replace("/etc/veci-sms-delivery-map",str(self.store))
        code=code.replace("/var/lock/veci-sms-delivery-map.lock",str(self.lock))
        code=code.replace("/etc/veci-sms-feature",str(d/"feature"))
        code=code.replace("/tmp/sysinfo/board_name",str(d/"board"))
        code=code.replace('[ "$(id -u)" = 0 ]','[ 0 = 0 ]')
        self.script=d/"worker"
        self.script.write_text(code)
        self.script.chmod(0o700)
    def tearDown(self):
        self.context.cleanup()
    def cmd(self,*args,pdu=""):
        return subprocess.run(["sh",str(self.script),*args],input=pdu,
                              capture_output=True,text=True,timeout=3)
    def test_track_and_deliver_and_no_status_downgrade(self):
        r=self.cmd("--track","18",pdu=PDU)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(json.loads(r.stdout),{"ok":True,"tracked":True})
        self.assertNotIn("12345678901",self.store.read_text())
        self.assertNotIn(PDU,self.store.read_text())
        r=self.cmd("--apply","18","+12345678901","0")
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        entry=json.loads(self.cmd("--list").stdout)["reports"][0]
        self.assertEqual(entry["state"],"delivered")
        self.assertEqual(entry["tp_st"],0)
        self.assertEqual(self.cmd("--apply","18","12345678901","32").returncode,0)
        self.assertEqual(json.loads(self.cmd("--list").stdout)["reports"][0]["state"],"delivered")
    def test_wrong_recipient_and_mr_never_deliver(self):
        self.assertEqual(self.cmd("--track","18",pdu=PDU).returncode,0)
        for args in [("19","12345678901","0"),("18","+21436587092","0")]:
            r=self.cmd("--apply",*args)
            self.assertNotEqual(r.returncode,0)
            self.assertNotIn("12345678901",r.stdout+r.stderr)
        entry=json.loads(self.cmd("--list").stdout)["reports"][0]
        self.assertEqual(entry["state"],"accepted")
    def test_ambiguous_mr_collision_blocks_delivery(self):
        self.assertEqual(self.cmd("--track","18",pdu=PDU).returncode,0)
        self.assertEqual(self.cmd("--track","18",pdu=OTHER).returncode,0)
        self.assertNotEqual(self.cmd("--apply","18","12345678901","0").returncode,0)
        self.assertTrue(all(e["state"]=="accepted" for e in json.loads(self.cmd("--list").stdout)["reports"]))
    def test_old_mr_is_not_reused_after_48_hours(self):
        self.assertEqual(self.cmd("--track","18",pdu=PDU).returncode,0)
        s=self.store.read_text().split("|")
        s[0]=str(int(time.time())-172801)
        self.store.write_text("|".join(s))
        self.assertNotEqual(self.cmd("--apply","18","12345678901","0").returncode,0)
    def test_fail_closed_on_invalid_input(self):
        self.assertNotEqual(self.cmd("--track","300",pdu=PDU).returncode,0)
        self.assertNotEqual(self.cmd("--track","18",pdu="AT+CMGD=1").returncode,0)
        self.assertNotEqual(self.cmd("--apply","18","not-a-number","0").returncode,0)
        self.assertEqual(self.store.read_text(),"")
    def test_busy_correlator_lock_denies_changes_and_reads(self):
        # A report arriving while a send is being tracked must fail closed,
        # not interleave its write or produce a stale state.
        with self.lock.open("w") as handle:
            fcntl.flock(handle,fcntl.LOCK_EX)
            for args in [("--track","18"),("--list",),("--apply","18","+12345678901","0")]:
                result=self.cmd(*args,pdu=PDU)
                self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertEqual(json.loads(result.stdout)["ok"],False)
            self.assertEqual(self.store.read_text(),"")
        self.assertEqual(self.cmd("--track","18",pdu=PDU).returncode,0)
        self.assertEqual(self.cmd("--apply","18","+12345678901","0").returncode,0)

    def test_sms_off_blocks_read_and_mutation(self):
        self.assertEqual(self.cmd("--track","18",pdu=PDU).returncode,0)
        self.script.parent.joinpath("feature").write_text("0")
        self.assertNotEqual(self.cmd("--list").returncode,0)
        self.assertNotEqual(self.cmd("--apply","18","12345678901","0").returncode,0)
if __name__=="__main__":unittest.main()
