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
 validate-apn) case "$2" in ""|*[!A-Za-z0-9._-]*) exit 1;; esac ;;
 status-fast) echo '{"modem_phase":"ready","registration_status":"registered","packet_status":"attached"}' ;;
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
                .replace("/usr/sbin/we5927-lte",str(manager))
                .replace("/var/lock/veci2-lte-policy.lock",str(root/"policy.lock"))
                .replace("/var/run/veci2-reboot-requested",str(root/"reboot-pending")))
        self.policy=root/"policy"
        self.policy.write_text((RUNTIME/"veci2-lte-policy").read_text()
          .replace("/tmp/sysinfo/board_name",str(board))
          .replace("/usr/sbin/we5927-lte",str(manager))
          .replace("/etc/config/we5927_lte",str(self.config))
          .replace("/var/lock/veci2-lte-policy.lock",str(root/"policy.lock"))
          .replace("/var/run/veci2-reboot-requested",str(root/"reboot-pending")))
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
        with (self.root/"policy.lock").open("w") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            self.assertEqual(self.call("switchSim",slot=2,confirmation="SWITCH_SIM_2")["error"],"busy")
        (self.root/"reboot-pending").touch()
        self.assertEqual(self.call("switchSim",slot=2,confirmation="SWITCH_SIM_2")["error"],"reboot_pending")
        (self.root/"reboot-pending").unlink()
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
        self.assertEqual(self.call("switchSim",slot=2,confirmation="SWITCH_SIM_2")["error"],"sim_switch_failed_previous_slot_restored")
        self.assertEqual(self.config.read_bytes(),before)
        self.assertEqual(self.slot.read_text(),"1\n")
        self.fail_sim.unlink()
        self.uci("-q","set","we5927_lte.main.apn=pending")
        self.assertEqual(self.call("switchSim",slot=2,confirmation="SWITCH_SIM_2")["error"],"pending_lte_changes")
        self.assertEqual(self.slot.read_text(),"1\n")
        self.uci("-q","revert","we5927_lte.main.apn")
        self.board.write_text("other-router\n")
        self.assertEqual(self.call("status")["error"],"unsupported_board")

    def test_native_policy_lifecycle_and_shared_lock(self):
        def policy(method,**payload):
            p=subprocess.run(["busybox","ash",str(self.policy),"call",method],input=json.dumps(payload),env=self.env,text=True,capture_output=True,timeout=8)
            self.assertEqual(p.returncode,0,p.stderr)
            return json.loads(p.stdout)
        with (self.root/"policy.lock").open("w") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            self.assertEqual(policy("setApn",apn="lab.example")["error"],"busy")
        before=self.config.read_bytes()
        for method,payload in (("setApn",{"apn":"bad apn"}),("setMonitor",{"interval":"60","expected":"99"}),("setFailover",{"action":"invalid"})):
            self.assertFalse(policy(method,**payload)["ok"])
            self.assertEqual(self.config.read_bytes(),before)
        self.assertEqual(policy("setApn",apn="lab.example")["configured_apn"],"lab.example")
        self.assertEqual(policy("setMonitor",interval="60",expected="10")["monitor_interval"],60)
        self.assertTrue(policy("setFailover",action="ENABLE_FAILOVER")["auto_failover"])
        self.assertEqual(self.call("switchSim",slot=2,confirmation="SWITCH_SIM_2")["error"],"disable_auto_failover_first")
        self.assertFalse(policy("setFailover",action="DISABLE_FAILOVER")["auto_failover"])
        self.assertEqual(self.slot.read_text(),"1\n")
        # A commit that writes then reports failure must restore original bytes.
        wrapper=self.root/"uci"; original=wrapper.read_text()
        wrapper.write_text(original.replace('exec "$HOST_UCI"','"$HOST_UCI"',1)+ 'rc=$?'+chr(10)+'case "$*" in *"commit we5927_lte") exit 1;; esac'+chr(10)+'exit "$rc"'+chr(10))
        before=self.config.read_bytes()
        self.assertEqual(policy("setApn",apn="rollback.example")["error"],"save_failed_rollback")
        self.assertEqual(self.config.read_bytes(),before)
        wrapper.write_text(original)
        self.assertEqual(policy("status")["configured_apn"],"lab.example")

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
