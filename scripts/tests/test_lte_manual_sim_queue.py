"""Exercise manual SIM handoff through the same consumer used by the LTE daemon."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "source/we5927-lte/files/usr/sbin/we5927-lte"
FUNCTIONS = SOURCE.read_text().rsplit('\ncase "$1" in', 1)[0]


class ManualSelectionTests(unittest.TestCase):
    def scenario(self, command):
        with tempfile.TemporaryDirectory() as tmp:
            driver = Path(tmp, "driver")
            driver.write_text(FUNCTIONS + """
SIM_REQUEST=$1/slot
level=1
clock=1000
date() { echo "$clock"; }
enabled() { return 0; }
selector_slot() { echo "$level"; }
set_sim() { echo "selected $1"; return 0; }
start_selected_sim() { echo "started $1"; [ "$1" = restore ] || [ "$ready" = yes ]; }
""" + command)
            return subprocess.run(["sh", driver, tmp], text=True, check=True,
                                  capture_output=True, timeout=4).stdout.splitlines()

    def test_reject_duplicate_queue_and_process_only_once(self):
        self.assertEqual(self.scenario("""
queue_sim 2 && ! queue_sim 2 && ready=yes && consume_sim_request &&
! consume_sim_request && cat "$SIM_REQUEST"
"""), ["selected 2", "started require_ready", "interface_started 1000 1 2"])

    def test_recovery_restores_measured_slot(self):
        self.assertEqual(self.scenario('queue_sim 2 && consume_sim_request && cat "$SIM_REQUEST"'),
                         ["selected 2", "started require_ready", "selected 1", "started restore",
                          "restored 1000 1 2"])

    def test_stale_or_changed_slot_does_not_actuate(self):
        for change, expected in [("clock=1181", "expired"), ("clock=99", "expired"),
                                 ("level=2", "selector_changed")]:
            self.assertEqual(self.scenario('queue_sim 2 && ' + change +
                                           ' && consume_sim_request && cat "$SIM_REQUEST"'),
                             [expected + " 1000 1 2"])

    def test_interrupted_consumer_never_repeats_radio_action(self):
        self.assertEqual(self.scenario('write_sim_request switching 1000 1 2 && '
                                       'consume_sim_request && cat "$SIM_REQUEST"'),
                         ["interrupted 1000 1 2"])

    def test_expired_status_without_daemon_allows_fresh_request(self):
        self.assertEqual(self.scenario('queue_sim 2 && clock=1200 && sim_request_status && '
                                       'queue_sim 2 && cat "$SIM_REQUEST"'), ["expired", "queued 1200 1 2"])

    def test_invalid_slot_and_same_slot_preserve_state(self):
        self.assertEqual(self.scenario('! queue_sim 0 && ! queue_sim 1 && [ ! -f "$SIM_REQUEST" ]'), [])

    def test_native_rpc_rejects_wrong_board_pending_changes_and_invalid_slot(self):
        runtime = ROOT / "rebuild/veci-v2/packages/veci-v2-runtime"
        acl = json.loads((runtime / "veci2-status-acl.json").read_text())["veci-v2-lte"]
        self.assertIn("queueSim", acl["write"]["ubus"]["veci.v2.lte"])
        self.assertNotIn("queueSim", acl["read"]["ubus"]["veci.v2.lte"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            board, manager, call_log = root / "board", root / "manager", root / "calls"
            provider = root / "provider"
            provider.write_text((runtime / "veci2-lte-policy").read_text()
                                .replace("/tmp/sysinfo/board_name", str(board))
                                .replace("/usr/sbin/we5927-lte", str(manager)))
            commands = {
                "manager": 'case "$1" in queue-sim) echo "$2" >> "$CALLS";; selector-slot) echo 1;; sim-request-status) echo queued;; validate-apn) exit 0;; esac',
                "jsonfilter": 'echo "$SLOT"',
                "uci": 'case "$2:$3" in changes:*) echo "$PENDING";; get:we5927_lte.main) echo modem;; get:*.sim) echo 1;; *) exit 1;; esac'
            }
            for name, body in commands.items():
                path = root / name
                path.write_text("#!/bin/sh\n" + body)
                path.chmod(0o700)
            def call(slot, pending=""):
                env = dict(os.environ, PATH=tmp + ":" + os.environ["PATH"], SLOT=slot,
                           PENDING=pending, CALLS=str(call_log))
                return json.loads(subprocess.check_output(["sh", provider, "call", "queueSim"],
                                  env=env, input=json.dumps({"slot": slot}), text=True, timeout=3))
            board.write_text("different-board")
            self.assertEqual(call("2")["error"], "unsupported_board")
            board.write_text("zbtlink,zbt-we5927")
            self.assertEqual(call("3")["error"], "invalid_slot")
            self.assertEqual(call("2", "pending")["error"], "pending_lte_changes")
            self.assertFalse(call_log.exists())
            reply = call("2")
            self.assertTrue(reply["ok"])
            self.assertEqual(reply["switch_state"], "queued")
            self.assertEqual(call_log.read_text(), "2\n")
