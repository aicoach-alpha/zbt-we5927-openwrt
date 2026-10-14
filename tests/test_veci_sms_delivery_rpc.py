"""Offline integration of v1.6.1 staged veci.sms RPC. No modem operations."""
import json
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
SOURCE=ROOT/"scripts/veci-sms-delivery-v161-staged/rpcd-veci.sms"
PDU="0021000B912143658709F1000005C82293F904"
LEGACY="0001000B912143658709F1000005C82293F904"

class DeliveryRpc(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        d=pathlib.Path(self.tmp.name)
        self.d=d
        (d/"bin").mkdir()
        (d/"feature").write_text("1")
        (d/"send_response").write_text('{"ok":true,"status":"accepted_by_modem","mr":18,"report_requested":true}\n')
        (d/"history_response").write_text('{"ok":true,"saved":true}\n')
        (d/"map_response").write_text('{"ok":true,"tracked":true}\n')
        (d/"view_response").write_text('{"ok":true,"source":"local_sent","count":0,"messages":[]}\n')
        def worker(name,text):
            f=d/name; f.write_text("#!/bin/sh\n"+text);f.chmod(0o700)
            return str(f)
        send=worker("send",'cat "$FIXTURE_DIR/send_response"\n')
        history=worker("history",'''case "$1" in
            --add) cat > "$FIXTURE_DIR/history_pdu"; cat "$FIXTURE_DIR/history_response";;
            --list) cat "$FIXTURE_DIR/view_response";;
            *) exit 9;; esac
        ''')
        mapper=worker("map",'''printf '%s %s\n' "$1" "$2" > "$FIXTURE_DIR/map_args"
            cat > "$FIXTURE_DIR/map_pdu"
            cat "$FIXTURE_DIR/map_response"
        ''')
        view=worker("view",'''[ "$1" = --list ] || exit 9
            cat "$FIXTURE_DIR/view_response"
        ''')
        filt=d/"bin/jsonfilter"
        filt.write_text('''#!/usr/bin/env python3
import json,sys
args=sys.argv[1:]
try:
    s=args[args.index("-s")+1]
    p=args[args.index("-e")+1].removeprefix("@.")
    print(json.loads(s)[p])
except (ValueError,KeyError,TypeError,IndexError):
    sys.exit(1)
''')
        filt.chmod(0o700)
        c=SOURCE.read_text()
        for old,new in [
            ("STATE_FILE=/etc/veci-sms-feature","STATE_FILE="+str(d/"feature")),
            ("SMS_SEND=/usr/libexec/veci-sms-send-one","SMS_SEND="+send),
            ("SENT_HISTORY=/usr/libexec/veci-sms-sent-history","SENT_HISTORY="+history),
            ("DELIVERY_MAP=/usr/libexec/veci-sms-delivery-map","DELIVERY_MAP="+mapper),
            ("DELIVERY_VIEW=/usr/libexec/veci-sms-sent-delivery-view","DELIVERY_VIEW="+view),
            ("SEND_RATE=/tmp/veci-sms-send-last-attempt","SEND_RATE="+str(d/"send_rate")),
            ("RATE_LOCK=/var/lock/veci-sms-inbox-rpc.lock","RATE_LOCK="+str(d/"rpc_lock")),
            ('[ "$(id -u)" -eq 0 ]','[ 0 -eq 0 ]'),
        ]:
            self.assertIn(old,c)
            c=c.replace(old,new)
        self.rpc=d/"rpc"
        self.rpc.write_text(c);self.rpc.chmod(0o700)
        self.env=os.environ.copy()
        self.env["FIXTURE_DIR"]=str(d)
        self.env["PATH"]=str(d/"bin")+os.pathsep+self.env.get("PATH","")
    def tearDown(self):
        self.tmp.cleanup()
    def rpc_call(self,method,pdu=PDU):
        inp=json.dumps({"pdu":pdu}) if method=="sendMessage" else "{}"
        return subprocess.run(["sh",str(self.rpc),"call",method],text=True,
                              input=inp,capture_output=True,timeout=5,env=self.env)
    def assert_ok(self,method,pdu=PDU):
        cp=self.rpc_call(method,pdu)
        self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
        return json.loads(cp.stdout)
    def test_delivery_tracking_after_modem_acceptance_and_history_commit(self):
        result=self.assert_ok("sendMessage")
        self.assertEqual(result,{"ok":True,"status":"accepted_by_modem",
                                  "history_saved":True,"delivery_tracking":True})
        self.assertEqual((self.d/"history_pdu").read_text(),PDU)
        self.assertEqual((self.d/"map_pdu").read_text(),PDU)
        self.assertEqual((self.d/"map_args").read_text().strip(),"--track 18")
    def test_legacy_is_never_tracked(self):
        (self.d/"send_response").write_text('{"ok":true,"status":"accepted_by_modem"}\n')
        result=self.assert_ok("sendMessage",LEGACY)
        self.assertEqual(result["history_saved"],True)
        self.assertEqual(result["delivery_tracking"],False)
        self.assertFalse((self.d/"map_args").exists())
    def test_history_persistence_failure_does_not_track(self):
        (self.d/"history_response").write_text('{"ok":false,"reason":"history_unavailable"}\n')
        result=self.assert_ok("sendMessage")
        self.assertEqual(result["history_saved"],False)
        self.assertEqual(result["delivery_tracking"],False)
        self.assertFalse((self.d/"map_args").exists())
    def test_unknown_or_rejected_never_writes_history(self):
        for reason in ["network_rejected","outcome_unknown","prompt_unavailable"]:
            with self.subTest(reason=reason):
                (self.d/"send_response").write_text(json.dumps({"ok":False,"reason":reason})+"\n")
                (self.d/"send_rate").unlink(missing_ok=True)
                result=self.assert_ok("sendMessage")
                self.assertEqual(result["reason"],reason)
                self.assertFalse((self.d/"history_pdu").exists())
                self.assertFalse((self.d/"map_pdu").exists())
    def test_bad_reference_does_not_mark_report_tracked(self):
        (self.d/"send_response").write_text('{"ok":true,"status":"accepted_by_modem","mr":600,"report_requested":true}\n')
        result=self.assert_ok("sendMessage")
        self.assertEqual(result["status"],"accepted_by_modem")
        self.assertEqual(result["delivery_tracking"],False)
        self.assertFalse((self.d/"map_args").exists())
    def test_failed_map_is_unconfirmed_not_failed_sms(self):
        (self.d/"map_response").write_text('{"ok":false,"reason":"delivery_unavailable"}\n')
        result=self.assert_ok("sendMessage")
        self.assertEqual(result["history_saved"],True)
        self.assertEqual(result["delivery_tracking"],False)
    def test_get_sent_uses_read_only_join(self):
        fixture={"ok":True,"source":"local_sent","count":1,
                 "messages":[{"at":1700000000,"pdu":PDU,
                              "status":"accepted_by_modem",
                              "delivery_status":"delivered","tp_st":0}]}
        (self.d/"view_response").write_text(json.dumps(fixture)+"\n")
        response=self.assert_ok("getSent")
        self.assertEqual(response,fixture)
        self.assertFalse((self.d/"map_pdu").exists())
    def test_no_operator_report_on_sms_disabled(self):
        (self.d/"feature").write_text("0")
        self.assertEqual(self.assert_ok("sendMessage")["reason"],"sms_disabled")
        self.assertFalse((self.d/"history_pdu").exists())

if __name__=="__main__":unittest.main()
