"""Exact-board manual dual-SIM RPC over disposable libuci and simulated modem."""
import fcntl,json,os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime"
PROVIDER=RUNTIME/"veci2-sim-manual"
HOST_UCI=os.environ.get("VECI_HOST_UCI") or ""

class ManualSimNativeAcceptance(unittest.TestCase):
    def setUp(self):
        self.assertTrue(HOST_UCI and Path(HOST_UCI).is_file(),"Requires native UCI, no silent skip")
        self.temp=tempfile.TemporaryDirectory(prefix="veci-sim-native-")
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        root=self.root
        cfg=root/"etc";cfg.mkdir()
        self.config=cfg/"we5927_lte"
        self.config.write_text("""config modem 'main'
 option sim_gpio '46'
 option sim1_value '1'
 option sim2_value '0'
 option usb_vid '05c6'
 option usb_pid '902e'
 option sim '1'
 option auto_failover '0'
""")
        board=root/"board";board.write_text("zbtlink,zbt-we5927\n")
        self.slot=root/"slot";self.slot.write_text("1\n")
        manager=root/"modem"
        manager.write_text("""#!/bin/sh
case "$1" in
 selector-slot) cat "$TEST_SLOT" ;;
 sim)
  case "$2" in 1|2) ;; *) exit 7 ;; esac
  if [ -e "$TEST_FAIL_SIM" ]; then exit 8; fi
  printf '%s\n' "$2" > "$TEST_SLOT"
  "$HOST_UCI" -c "$TEST_CFG" -t "$TEST_DELTA" set "we5927_lte.main.sim=$2" ||
      exit 9
  "$HOST_UCI" -c "$TEST_CFG" -t "$TEST_DELTA" commit we5927_lte || exit 10
 ;;
 *) exit 11 ;;
esac
""")
        manager.chmod(0o755)
        filt=root/"jsonfilter"
        filt.write_text("""#!/usr/bin/env python3
import json,sys
args=sys.argv[1:]; raw=args[args.index('-s')+1]
field=args[args.index('-e')+1].removeprefix('@.')
data=json.loads(raw)
if field not in data:sys.exit(1)
print(data[field])
""")
        filt.chmod(0o755)
        uci=root/"uci"
        uci.write_text('#!/bin/sh\nexec "$HOST_UCI" -c "$TEST_CFG" -t "$TEST_DELTA" "$@"\n')
        uci.chmod(0o755)
        program=root/"provider"
        program.write_text(PROVIDER.read_text().replace("/tmp/sysinfo/board_name",str(board))
                .replace("/usr/sbin/we5927-lte",str(manager)))
        self.program=program
        self.board=board
        self.fail_sim=root/"fail-sim"
        self.delta=root/"delta";self.delta.mkdir()
        self.env={**os.environ, "PATH":str(root)+":"+os.environ["PATH"],
                  "HOST_UCI":HOST_UCI,"TEST_CFG":str(cfg),"TEST_DELTA":str(self.delta),
                  "TEST_SLOT":str(self.slot),"TEST_FAIL_SIM":str(self.fail_sim)}
    def uci(self,*args):
        return subprocess.run([str(self.root/"uci"),*args],env=self.env,
            capture_output=True,text=True,timeout=4)
    def call(self,method,**payload):
        p=subprocess.run(["bash",str(self.program),"call",method],input=json.dumps(payload),
                         env=self.env,capture_output=True,text=True,timeout=9)
        self.assertEqual(p.returncode,0,p.stderr+"\n"+p.stdout)
        return json.loads(p.stdout)

    def test_native_manual_sim_switch_confirmation_and_uci_consistency(self):
        self.assertEqual(self.call("status")["selector_slot"],1)
        for req in ({},{"slot":2,"confirmation":"SWITCH_SIM_1"},
                    {"slot":3,"confirmation":"SWITCH_SIM_3"},
                    {"slot":2,"confirmation":"yes"}):
            with self.subTest(request=req):
                self.assertFalse(self.call("switchSim",**req)["ok"])
                self.assertEqual(self.slot.read_text(),"1\n")
        changed=self.call("switchSim",slot=2,confirmation="SWITCH_SIM_2")
        self.assertTrue(changed["ok"],changed)
        self.assertEqual(changed["selector_slot"],2)
        self.assertEqual(changed["configured_slot"],2)
        self.assertEqual(self.uci("-q","get","we5927_lte.main.sim").stdout.strip(),"2")
        self.assertEqual(self.call("status")["selector_slot"],2)
        changed=self.call("switchSim",slot=1,confirmation="SWITCH_SIM_1")
        self.assertTrue(changed["ok"],changed)
        self.assertEqual(self.uci("-q","get","we5927_lte.main.sim").stdout.strip(),"1")

    def test_rollback_pending_and_wrong_board_fail_closed(self):
        before=self.config.read_bytes()
        self.fail_sim.touch()
        self.assertEqual(self.call("switchSim",slot=2,confirmation="SWITCH_SIM_2")["error"],
                         "sim_switch_failed_previous_slot_restored")
        self.assertEqual(self.config.read_bytes(),before)
        self.assertEqual(self.slot.read_text(),"1\n")
        self.fail_sim.unlink()
        self.uci("-q","set","we5927_lte.main.apn=pending")
        self.assertEqual(self.call("switchSim",slot=2,confirmation="SWITCH_SIM_2")["error"],"pending_lte_changes")
        self.assertEqual(self.slot.read_text(),"1\n")
        self.uci("-q","revert","we5927_lte.main.apn")
        self.board.write_text("other-router\n")
        self.assertEqual(self.call("status")["error"],"unsupported_board")

    def test_acl_scoping_and_derived_modem_config_guards(self):
        acl=json.loads((RUNTIME/"veci2-status-acl.json").read_text())
        self.assertIn("veci.v2.sim",json.dumps(acl))
        source=PROVIDER.read_text()
        for guard in ("wrong_sim_selector","wrong_modem_identity","selector_config_mismatch",
                      "disable_auto_failover_first","flock -n 9","explicit_confirmation_required"):
            self.assertIn(guard,source)
        self.assertNotIn("AT+CFUN",source)
        subprocess.run(["busybox","ash","-n",str(PROVIDER)],check=True,capture_output=True,timeout=4)

if __name__=="__main__":unittest.main()
