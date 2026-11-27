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
        data=data.replace("/etc/config/network",str(network)).replace("/usr/libexec/veci2-lan-bounds",str(RUNTIME/"veci2-lan-bounds")).replace("/var/lock/veci2-ipv6.lock",str(self.root/"network.lock")).replace("/var/run/veci2-reboot-requested",str(self.root/"reboot-pending")).replace("/etc/nftables.d/90-veci-ttl.nft",str(self.root/"ttl.nft"))
        data=data.replace("/etc/init.d/firewall",str(reloadscript))
        data=data.replace("/usr/share/libubox/jshn.sh",str(Path(LIBUBOX)/"share/libubox/jshn.sh"))
        (self.root/"nftables.d").mkdir()
        data=data.replace("/etc/nftables.d",str(self.root/"nftables.d"))
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
case "$4" in
  192.168.1.0|192.168.1.1|192.168.1.255) echo "unreachable $4" ;;
  192.168.1.*) printf '%s dev br-lan\\n' "$4" ;;
  *) echo "unreachable $4" ;;
esac
""")
        ip.chmod(0o755)
        fw4=self.root/"fw4"
        fw4.write_text('#!/bin/sh\n[ "$*" = check ] || exit 99\n[ "${FAIL_FW:-0}" = 0 ]\n')
        fw4.chmod(0o755)
        nft=self.root/"nft"
        nft.write_text("""#!/bin/sh
case "$*" in
 'list table inet fw4') [ ! -f "$TABLE_MISSING" ];;
 'list chain inet fw4 veci_ttl_forward') [ -f "$TTL_FILE" ] && cat "$TTL_FILE";;
 *) exit 99;;
esac
""")
        nft.chmod(0o700)
        self.delta=self.root/"delta"
        self.delta.mkdir()
        self.call_log=self.root/"called.log"
        self.env=dict(os.environ,HOST_UCI=UCI_HOST,TEST_CFG=str(self.config),
                      TEST_DELTA=str(self.delta),TTL_FILE=str(self.root/"ttl.nft"),TABLE_MISSING=str(self.root/"table-missing"),RELOAD_FAIL_ONCE=str(self.failflag),JSON_PREFIX="",JSON_UNSET="",JSON_SEQ="0",JSON_CUR="J_V",FAKE_CALL_LOG=str(self.call_log),
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
        self.assertEqual(sum(x["name"]=="veci_port_tcp_8082" for x in added["forwards"]),1,added)
        self.assertEqual(sum(x["source_port"]=="8082" for x in added["forwards"]),1,added)
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

    def test_cidr_destination_overlap_and_ownership(self):
        for cmd in (("set","network.lan.ipaddr=192.168.1.1/24"),("delete","network.lan.netmask"),("commit","network")):
            self.assertEqual(self.uci(*cmd).returncode,0)
        args=dict(from_port=8443,to_port=443,protocol="tcp",destination="192.168.1.23",confirmation="FORWARD_8443")
        before=self.firewall.read_bytes()
        self.assertEqual(self.call("addForward",**args)["error"],"overlapping_or_unverified_redirect")
        self.assertEqual(self.firewall.read_bytes(),before)
        args.update(from_port=8083,confirmation="FORWARD_8083")
        self.assertTrue(self.call("addForward",**args)["ok"])
        self.uci("set","firewall.veci_port_tcp_8083.name=Foreign")
        self.uci("commit","firewall")
        before=self.firewall.read_bytes()
        self.assertEqual(self.call("deleteForward",name="veci_port_tcp_8083",confirmation="DELETE_veci_port_tcp_8083")["error"],"not_owner_redirect")
        self.assertEqual(self.firewall.read_bytes(),before)
        import fcntl
        with (self.root/"network.lock").open("w") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            self.assertEqual(self.call("addForward",**args)["error"],"network_busy")
        self.assertEqual(self.firewall.read_bytes(),before)
    def test_native_defaults_and_software_offload(self):
        rev=self.call("status")["revision"]
        args=dict(drop_invalid="1",syn_flood="1",revision=rev,confirmation="SAVE_FIREWALL_DEFAULTS")
        before=self.firewall.read_bytes()
        self.failflag.touch()
        self.assertEqual(self.call("setDefaults",**args)["error"],"firewall_apply_failed_rollback_attempted")
        self.assertEqual(self.firewall.read_bytes(),before)
        saved=self.call("setDefaults",**args)
        self.assertTrue(saved["ok"],saved)
        self.assertEqual(self.uci("get","firewall.@defaults[0].synflood_protect").stdout.strip(),"1")
        offload=dict(enabled="1",revision=saved["revision"],confirmation="SAVE_SOFTWARE_OFFLOAD")
        result=self.call("setOffload",**offload)
        self.assertTrue(result["ok"],result)
        self.assertEqual(self.uci("get","firewall.@defaults[0].flow_offloading_hw").stdout.strip(),"0")
        self.assertEqual(self.uci("get","firewall.@defaults[0].flow_offloading").stdout.strip(),"1")
        self.assertEqual(self.call("setOffload",**offload)["error"],"stale_configuration")
        blocked=self.call("setMacBlock",addresses="02:00:00:00:00:01",revision=result["revision"],confirmation="SAVE_MAC_BLOCK")
        self.assertTrue(blocked["ok"],blocked)
        self.assertEqual(self.call("setOffload",**(offload|dict(revision=blocked["revision"])))["error"],"mac_block_requires_offload_disabled")

    def test_native_mac_list_acl_and_parent_lifecycle(self):
        mac="02:00:00:00:00:01"; other="02:00:00:00:00:02"
        rev=self.call("status")["revision"]
        result=self.call("setMacBlock",addresses=mac+" "+other+" "+mac,revision=rev,confirmation="SAVE_MAC_BLOCK")
        self.assertTrue(result["ok"],result)
        self.assertEqual(result["blocked_macs"],[mac,other])
        before=self.firewall.read_bytes()
        self.assertEqual(self.call("setMacBlock",addresses="",revision=rev,confirmation="SAVE_MAC_BLOCK")["error"],"stale_configuration")
        self.failflag.touch()
        self.assertEqual(self.call("setMacBlock",addresses="",revision=result["revision"],confirmation="SAVE_MAC_BLOCK")["error"],"firewall_apply_failed_rollback_attempted")
        self.assertEqual(self.firewall.read_bytes(),before)
        cleared=self.call("setMacBlock",addresses="",revision=result["revision"],confirmation="SAVE_MAC_BLOCK")
        self.assertEqual(cleared["blocked_macs"],[])
        for method,read,confirm,delete,section in (
          ("saveAcl","aclStatus","SAVE_LAN_ACL","DELETE_LAN_ACL","veci_acl_1"),
          ("saveParent","parentStatus","SAVE_PARENT_SCHEDULE","DELETE_PARENT_SCHEDULE","veci_parent_1")):
            args=dict(slot="1",mac=mac,enabled="1",action="save",revision=self.call(read)["revision"],confirmation=confirm)
            if method=="saveParent":args.update(start_time="08:00:00",stop_time="09:00:00",weekdays="Monday Friday")
            result=self.call(method,**args)
            self.assertTrue(result["ok"],result)
            self.assertEqual(result["rules"][0]["enabled"],"1")
            self.assertEqual(result["rules"][0]["mac"],mac)
            if method=="saveParent":
                self.assertEqual(result["rules"][0]["timezone"],"UTC")
                self.assertEqual(result["rules"][0]["weekdays"],"Monday Friday")
            offload=self.call("setOffload",enabled="1",revision=result["revision"],confirmation="SAVE_SOFTWARE_OFFLOAD")
            self.assertEqual(offload["error"],"acl_requires_offload_disabled")
            args.update(revision=result["revision"],enabled="0")
            result=self.call(method,**args)
            self.assertTrue(result["ok"],result)
            self.assertEqual(result["rules"][0]["enabled"],"0")
            before=self.firewall.read_bytes()
            self.failflag.touch()
            args.update(revision=result["revision"],action="delete",confirmation=delete)
            self.assertEqual(self.call(method,**args)["error"],"firewall_apply_failed_rollback_attempted")
            self.assertEqual(self.firewall.read_bytes(),before)
            self.assertEqual(self.call(method,**args)["rules"],[])
            self.assertNotEqual(self.uci("-q","get","firewall."+section).returncode,0)
    def test_foreign_rule_extra_conditions_are_not_overwritten(self):
        args=dict(slot="1",mac="02:00:00:00:00:01",enabled="1",action="save",revision=self.call("aclStatus")["revision"],confirmation="SAVE_LAN_ACL")
        self.assertTrue(self.call("saveAcl",**args)["ok"])
        self.uci("set","firewall.veci_acl_1.dest_port=443");self.uci("commit","firewall")
        before=self.firewall.read_bytes()
        import hashlib
        args["revision"]=hashlib.sha256(before).hexdigest()
        self.assertEqual(self.call("saveAcl",**args)["error"],"foreign_acl_slot")
        self.assertEqual(self.call("aclStatus")["error"],"foreign_acl_slot")
        self.assertEqual(self.firewall.read_bytes(),before)

    def test_ttl_state_and_rollback(self):
        initial=self.call("ttlStatus")
        args=dict(enabled="1",ttl="64",revision=initial["revision"],confirmation="ENABLE_FORWARD_TTL")
        (self.root/"reboot-pending").touch()
        self.assertEqual(self.call("setTtl",**args)["error"],"reboot_pending")
        (self.root/"reboot-pending").unlink()
        self.failflag.touch()
        self.assertEqual(self.call("setTtl",**args)["error"],"ttl_apply_failed_rollback_attempted")
        self.assertFalse((self.root/"ttl.nft").exists())
        saved=self.call("setTtl",**args)
        self.assertEqual(saved["runtime"],"rule_present",saved)
        self.assertFalse(saved["packet_verified"])
        disable=dict(enabled="0",revision=saved["revision"],confirmation="DISABLE_FORWARD_TTL")
        (self.root/"table-missing").touch()
        self.assertEqual(self.call("setTtl",**disable)["error"],"ttl_apply_failed_rollback_attempted")
        self.assertTrue((self.root/"ttl.nft").exists())
        (self.root/"table-missing").unlink()
        self.assertEqual(self.call("setTtl",**disable)["runtime"],"rule_absent")
    def test_acl_scope_and_no_wan_policy_relaxation(self):
        acl=json.loads((RUNTIME/"veci2-status-acl.json").read_text())["veci-v2-firewall"]
        self.assertEqual(set(acl["read"]["ubus"]["veci.v2.firewall"]),{"status","ttlStatus","aclStatus","parentStatus"})
        self.assertEqual(set(acl["write"]["ubus"]["veci.v2.firewall"]),
                         {"addForward","deleteForward","setDmz","setDefaults","setOffload","setMacBlock","saveAcl","saveParent","setTtl"})
        self.assertIn("unsafe_wan_policy",SOURCE.read_text())
        subprocess.run(["busybox","ash","-n",str(SOURCE)],check=True)

if __name__=="__main__":
    unittest.main()
