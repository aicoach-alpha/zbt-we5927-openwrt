"""Offline tests of v1.6.1 Sent History + Delivery map joining; no AT I/O."""
import fcntl
import hashlib
import json
import pathlib
import subprocess
import tempfile
import time
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
SOURCE=ROOT/"scripts/veci-sms-delivery-v161-staged/veci-sms-sent-delivery-view"
PDU="0021000B912143658709F1000005C82293F904"
OTHER="0021000B912143658709F1000003C14021"
LEGACY="0001000B912143658709F1000005C82293F904"

class SentDeliveryView(unittest.TestCase):
    def setUp(self):
        self.context=tempfile.TemporaryDirectory()
        d=pathlib.Path(self.context.name)
        self.history=d/"history"
        self.mapping=d/"mapping"
        self.feature=d/"feature"
        self.board=d/"board"
        self.lock=d/"lock"
        self.history.write_text("")
        self.mapping.write_text("")
        self.feature.write_text("1")
        self.board.write_text("zbtlink,zbt-we5927")
        source=SOURCE.read_text()
        for old,new in [
            ("/etc/veci-sms-sent-history",str(self.history)),
            ("/etc/veci-sms-delivery-map",str(self.mapping)),
            ("/etc/veci-sms-feature",str(self.feature)),
            ("/tmp/sysinfo/board_name",str(self.board)),
            ("/var/lock/veci-sms-delivery-map.lock",str(self.lock)),
            ('[ "$(id -u)" -eq 0 ]','[ 0 -eq 0 ]'),
        ]:
            source=source.replace(old,new)
        self.script=d/"view"
        self.script.write_text(source)
        self.script.chmod(0o700)
    def tearDown(self):
        self.context.cleanup()
    def run_view(self):
        return subprocess.run(["sh",str(self.script),"--list"],capture_output=True,
                              text=True,timeout=4)
    def put_history(self, pdu=PDU, at=None):
        at=at or int(time.time())
        with self.history.open("a") as f:
            f.write(f"{at}|{pdu}\n")
        return at
    def put_map(self,pdu=PDU,state="delivered",st=0,at=None,mr=18,
                recipient="12345678901"):
        at=at or int(time.time())
        rh=hashlib.sha256(recipient.encode()).hexdigest()
        ph=hashlib.sha256(pdu.encode()).hexdigest()
        with self.mapping.open("a") as f:
            f.write(f"{at}|{mr}|{rh}|{ph}|{state}|{st}\n")
    def messages(self):
        result=self.run_view()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        obj=json.loads(result.stdout)
        self.assertTrue(obj["ok"])
        self.assertEqual(obj["source"],"local_sent")
        self.assertEqual(obj["count"],len(obj["messages"]))
        return obj["messages"]
    def test_verified_delivered_without_losing_existing_sent_history_schema(self):
        at=self.put_history()
        self.put_map(at=at+2)
        records=self.messages()
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]["status"],"accepted_by_modem")
        self.assertEqual(records[0]["delivery_status"],"delivered")
        self.assertEqual(records[0]["tp_st"],0)
        self.assertEqual(records[0]["pdu"],PDU)
    def test_no_report_and_accepted_never_forge_delivered(self):
        at=self.put_history()
        self.assertEqual(self.messages()[0]["delivery_status"],"unconfirmed")
        self.put_map(at=at,state="accepted",st=255)
        self.assertEqual(self.messages()[0]["delivery_status"],"awaiting_report")
    def test_terminal_and_interim_report_status(self):
        at=self.put_history()
        self.put_map(at=at,state="pending",st=32)
        self.assertEqual(self.messages()[0]["delivery_status"],"pending")
        self.mapping.write_text("")
        self.put_map(at=at,state="failed",st=64)
        self.assertEqual(self.messages()[0]["delivery_status"],"failed")
    def test_duplicate_history_or_map_denies_confident_status(self):
        at=self.put_history()
        self.put_map(at=at)
        self.put_history(PDU,at+1)
        self.assertEqual([x["delivery_status"] for x in self.messages()],
                         ["unconfirmed","unconfirmed"])
        self.history.write_text(f"{at}|{PDU}\n")
        self.put_map(at=at+1,mr=19)
        self.assertEqual(self.messages()[0]["delivery_status"],"unconfirmed")
    def test_legacy_pdu_never_matches_even_if_hash_was_added(self):
        at=self.put_history(LEGACY)
        self.put_map(pdu=LEGACY,at=at)
        self.assertEqual(self.messages()[0]["delivery_status"],"unconfirmed")
    def test_stale_or_future_tracking_time_is_not_confident(self):
        now=int(time.time())
        self.put_history(at=now-600)
        self.put_map(at=now)
        self.assertEqual(self.messages()[0]["delivery_status"],"unconfirmed")
    def test_corrupt_map_and_history_are_not_exposed(self):
        at=self.put_history()
        self.put_map(at=at)
        self.mapping.write_text(self.mapping.read_text().replace("|delivered|0","|delivered|255"))
        failed=self.run_view()
        self.assertNotEqual(failed.returncode,0)
        self.assertNotIn(PDU,failed.stdout+failed.stderr)
        self.mapping.write_text("")
        self.history.write_text(f"{at}|AT+CMGD=1\n")
        failed=self.run_view()
        self.assertNotEqual(failed.returncode,0)
        self.assertNotIn("AT+CMGD=1",failed.stdout+failed.stderr)
    def test_busy_lock_fails_closed(self):
        self.put_history()
        with self.lock.open("w") as handle:
            fcntl.flock(handle,fcntl.LOCK_EX)
            result=self.run_view()
            self.assertNotEqual(result.returncode,0)
            self.assertNotIn(PDU,result.stdout)
    def test_disabled_sms_denies_view(self):
        self.put_history()
        self.feature.write_text("0")
        result=self.run_view()
        self.assertNotEqual(result.returncode,0)
        self.assertNotIn(PDU,result.stdout)
    def test_bounded_30_messages(self):
        now=int(time.time())
        for i in range(30):
            self.put_history(PDU,now+i)
        self.assertEqual(len(self.messages()),30)
        self.put_history(PDU,now+31)
        self.assertNotEqual(self.run_view().returncode,0)

if __name__=="__main__":
    unittest.main()
