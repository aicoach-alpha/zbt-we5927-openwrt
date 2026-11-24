"""Native libuci/firewall provider sandbox: actual UCI stages, rollback and ACL."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime"
SOURCE=RUNTIME/"veci2-firewall"
UCI_HOST=os.environ.get("VECI_HOST_UCI") or ""
LIBUBOX=os.environ.get("VECI_LIBUBOX_PREFIX") or ""


class NativeFirewallAcceptance(unittest.TestCase):
    def setUp(self):
        self.assertTrue(UCI_HOST and Path(UCI_HOST).is_file(),"Native UCI required; never silently skip")
        self.assertTrue(LIBUBOX and (Path(LIBUBOX)/"share/libubox/jshn.sh").is_file(),"Host libubox required")
        self.temp=tempfile.TemporaryDirectory(prefix="veci-firewall-native-")
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.config=self.root/"etc"
        self.config.mkdir()
        self.firewall=self.config/"firewall"
        self.firewall.write_text("""config defaults 'defaults'
  option input 'ACCEPT'
  option forward 'REJECT'
config zone 'lan'
  option name 'lan'
  option input 'ACCEPT'
  option forward 'ACCEPT'
config zone 'wan'
  option name 'wan'
  option input 'REJECT'
  option forward 'REJECT'
  option masq '1'
config redirect 'external_rule'
  option name 'ExternalUnaffected'
  option src 'wan'
  option dest 'lan'
  option proto 'tcp'
  option src_dport '8443'
  option dest_ip '192.168.1.4'
  option dest_port '443'
  option target 'DNAT'
""")
        network=self.config/"network"
        network.write_text("""config interface 'lan'
  option device 'br-lan'
  option proto 'static'
  option ipaddr '192.168.1.1'
  option netmask '255.255.255.0'
""")
        self.old=self.firewall.read_bytes()
        board=self.root/"board";board.write_text("zbtlink,zbt-we5927\n")
        self.failflag=self.root/"fail-once"
        reloadscript=self.root/"restart"
        reloadscript.write_text("""#!/bin/sh
if test -f "$RELOAD_FAIL_ONCE"; then rm -f "$RELOAD_FAIL_ONCE"; exit 1; fi
exit 0
""")
        reloadscript.chmod(0o755)
        program=self.root/"provider"
        data=SOURCE.read_text()
        data=data.replace("/tmp/sysinfo/board_name",str(board))
        data=data.replace("/etc/config/firewall",str(self.firewall))
        data=data.replace("/etc/init.d/firewall",str(reloadscript))
        data=data.replace("/usr/share/libubox/jshn.sh",str(Path(LIBUBOX)/"share/libubox/jshn.sh"))
        program.write_text(data)
        program.chmod(0o755)
        self.program=program
        uci=self.root/"uci"
        uci.write_text('#!/bin/sh\nexec "$HOST_UCI" -c "$TEST_CFG" -t "$TEST_DELTA" "$@"\n')
        uci.chmod(0o755)
        filt=self.root/"jsonfilter"
        filt.write_text("""#!/usr/bin/env python3
import json,sys
argv=sys.argv[1:]
raw=argv[argv.index('-s')+1]
key=argv[argv.index('-e')+1].removeprefix('@.')
value=json.loads(raw).get(key)
if value is None:sys.exit(1)
print(value)
""")
        filt.chmod(0o755)
        calc=self.root/"ipcalc.sh"
        calc.write_text("#!/bin/sh\necho \"CALC:$*\" >> \"$FAKE_CALL_LOG\"\nprintf 'NETWORK=192.168.1.0\\n'\n")
        calc.chmod(0o755)
        ip=self.root/"ip"
        ip.write_text("""#!/bin/sh
case "$3" in
  192.168.1.0|192.168.1.1|192.168.1.255) echo "unreachable $3" ;;
  192.168.1.*) printf 'local %s dev br-lan\\n' "$3" ;;
  *) echo "unreachable $3" ;;
esac
""")
        ip.chmod(0o755)
        self.delta=self.root/"delta"
        self.delta.mkdir()
        self.call_log=self.root/"called.log"
        self.env=dict(os.environ,HOST_UCI=UCI_HOST,TEST_CFG=str(self.config),
                      TEST_DELTA=str(self.delta),RELOAD_FAIL_ONCE=str(self.failflag),JSON_PREFIX="",JSON_UNSET="",JSON_SEQ="0",JSON_CUR="J_V",FAKE_CALL_LOG=str(self.call_log),
                      PATH=str(self.root)+":"+LIBUBOX+"/bin:"+os.environ["PATH"],
                      LD_LIBRARY_PATH=LIBUBOX+"/lib:"+os.environ.get("LD_LIBRARY_PATH",""))
    def uci(self, *args):
        proc=subprocess.run([str(self.root/"uci"),*args],env=self.env,
            capture_output=True,text=True,timeout=6)
        return proc
    def call(self,method,**data):
        run=subprocess.run(["bash",str(self.program),"call",method],
            input=json.dumps(data),env=self.env,capture_output=True,text=True,timeout=10)
        self.assertEqual(run.returncode,0,run.stderr+"\n"+run.stdout)
        return json.loads(run.stdout)

    def test_real_forward_crud_native_uci_and_owned_rule_deletion(self):
        initial=self.call("status")
        self.assertEqual(initial["wan_input"],"REJECT")
        self.assertEqual(self.uci("-q","get","firewall.external_rule.name").stdout.strip(),"ExternalUnaffected")
        added=self.call("addForward",from_port=8082,to_port=80,protocol="tcp",
            destination="192.168.1.23",confirmation="FORWARD_8082")
        self.assertTrue(added["ok"],added)
        self.assertEqual(self.uci("-q","get","firewall.veci_port_tcp_8082.dest_ip").stdout.strip(),"192.168.1.23")
        self.assertEqual(self.uci("-q","get","firewall.@zone[1].input").stdout.strip(),"REJECT")
        self.assertEqual(self.uci("-q","get","firewall.external_rule.name").stdout.strip(),"ExternalUnaffected")
        self.assertEqual(self.call("addForward",from_port=8082,to_port=80,protocol="tcp",
               destination="192.168.1.23",confirmation="FORWARD_8082")["error"],"port_forward_already_exists")
        self.assertEqual(self.call("deleteForward",name="external_rule",confirmation="DELETE_external_rule")["error"],"not_owner_redirect")
        self.assertTrue(self.call("deleteForward",name="veci_port_tcp_8082",
                                  confirmation="DELETE_veci_port_tcp_8082")["ok"])
        self.assertNotEqual(self.uci("-q","get","firewall.veci_port_tcp_8082").returncode,0)
        self.assertEqual(self.uci("-q","get","firewall.external_rule.name").stdout.strip(),"ExternalUnaffected")

    def test_native_dmz_requires_confirmation_and_rolls_back_reload_failure(self):
        original=self.firewall.read_bytes()
        unexpected=self.call("setDmz",destination="192.168.1.22",confirmation="bad")
        self.assertEqual(unexpected["error"],"confirmation_required")
        self.assertEqual(self.firewall.read_bytes(),original)
        self.failflag.touch()
        failure=self.call("setDmz",destination="192.168.1.22",
             confirmation="ENABLE_DMZ_192.168.1.22")
        self.assertEqual(failure["error"],"firewall_apply_failed_rollback_attempted")
        self.assertEqual(self.firewall.read_bytes(),original)
        result=self.call("setDmz",destination="192.168.1.22",
                confirmation="ENABLE_DMZ_192.168.1.22")
        self.assertTrue(result["ok"],result)
        self.assertEqual(self.uci("-q","get","firewall.veci_owner_dmz.dest_ip").stdout.strip(),"192.168.1.22")
        self.assertTrue(self.call("setDmz",destination="DISABLE",confirmation="DISABLE_DMZ")["ok"])
        self.assertNotEqual(self.uci("-q","get","firewall.veci_owner_dmz").returncode,0)
        self.assertEqual(self.uci("-q","get","firewall.external_rule.name").stdout.strip(),"ExternalUnaffected")

    def test_invalid_inputs_leave_real_uci_byte_unchanged(self):
        before=self.firewall.read_bytes()
        bad=[
            {"from_port":22,"to_port":80,"protocol":"tcp","destination":"192.168.1.23","confirmation":"FORWARD_22"},
            {"from_port":23,"to_port":80,"protocol":"tcp","destination":"192.168.1.23","confirmation":"FORWARD_23"},
            {"from_port":0,"to_port":80,"protocol":"tcp","destination":"192.168.1.23","confirmation":"FORWARD_0"},
            {"from_port":65536,"to_port":80,"protocol":"tcp","destination":"192.168.1.23","confirmation":"FORWARD_65536"},
            {"from_port":23,"to_port":80,"protocol":"sctp","destination":"192.168.1.23","confirmation":"FORWARD_23"},
            {"from_port":8082,"to_port":80,"protocol":"tcp","destination":"192.168.2.4","confirmation":"FORWARD_8082"},
            {"from_port":8082,"to_port":80,"protocol":"tcp","destination":"192.168.1.1","confirmation":"FORWARD_8082"},
        ]
        for entry in bad:
            with self.subTest(entry=entry):
                ret=self.call("addForward",**entry)
                self.assertFalse(ret["ok"],ret)
                self.assertEqual(before,self.firewall.read_bytes())
        self.assertEqual(self.uci("-q","get","firewall.external_rule.name").stdout.strip(),"ExternalUnaffected")

    def test_acl_scope_and_no_wan_policy_relaxation(self):
        acl=json.loads((RUNTIME/"veci2-status-acl.json").read_text())["veci-v2-firewall"]
        self.assertEqual(acl["read"]["ubus"]["veci.v2.firewall"],["status"])
        self.assertEqual(set(acl["write"]["ubus"]["veci.v2.firewall"]),
                         {"addForward","deleteForward","setDmz"})
        self.assertIn("unsafe_wan_policy",SOURCE.read_text())
        subprocess.run(["busybox","ash","-n",str(SOURCE)],check=True)

if __name__=="__main__":
    unittest.main()
