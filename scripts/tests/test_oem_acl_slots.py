"""Native ACL inventory and fail-closed mutation checks; no live firewall writes."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[2] / "rebuild/veci-v2/packages/veci-v2-runtime/veci2-firewall"

class AclSlots(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.d = Path(t.name)
        (self.d/"board").write_text("zbtlink,zbt-we5927\n")
        (self.d/"firewall").write_text("fixture\n")
        (self.d/"jshn").write_text("""
json_init() { :; }
json_add_boolean() { printf '%s=%s\\n' "$1" "$2"; }
json_add_string() { printf '%s=%s\\n' "$1" "$2"; }
json_add_array() { :; }
json_add_object() { :; }
json_close_object() { :; }
json_close_array() { :; }
json_dump() { :; }
""")
        s=BASE.read_text()
        for old,new in (("/tmp/sysinfo/board_name","board"),("/etc/config/firewall","firewall"),("/usr/share/libubox/jshn.sh","jshn")):
            s=s.replace(old,str(self.d/new))
        (self.d/"rpc").write_text(s)
        self.cmd("uci", """case "$2" in
 changes) exit 0;;
 get) case "$3" in
 firewall.@zone*) :;;
 esac;;
 *) echo MUTATION_ATTEMPT >&2; exit 99;;
esac
case "$3" in
 'firewall.@zone[0].name') echo lan;;
 'firewall.@zone[1].name') echo wan;;
 'firewall.@zone[1].input') echo REJECT;;
 firewall.veci_acl_1) echo rule;;
 firewall.veci_acl_1.name) echo "${OWNER:-VeCI_ACL_veci_acl_1}";;
 firewall.veci_acl_1.src) echo lan;;
 firewall.veci_acl_1.dest) echo wan;;
 firewall.veci_acl_1.target) echo REJECT;;
 firewall.veci_acl_1.proto) echo all;;
 firewall.veci_acl_1.family) echo any;;
 firewall.veci_acl_1.src_mac) echo "${MAC:-aa:bb:cc:dd:ee:ff}";;
 firewall.veci_acl_1.enabled) echo "${ENABLED:-1}";;
 'firewall.@defaults[0]') echo defaults;;
 *) exit 1;;
esac""")
        self.cmd("jsonfilter", """exec python3 -c 'import json,sys; print(json.loads(sys.argv[1])[sys.argv[2][2:]])' "$2" "$4" """)
    def cmd(self,name,body):
        p=self.d/name;p.write_text("#!/bin/sh\n"+body+"\n");p.chmod(0o755)
    def run_rpc(self,method,body="",**env):
        return subprocess.run(["sh",str(self.d/"rpc"),"call",method],input=body,
            env=dict(os.environ,PATH=str(self.d)+":"+os.environ["PATH"],**env),
            text=True,capture_output=True,timeout=5)
    def test_inventory_and_foreign_owner(self):
        r=self.run_rpc("aclStatus")
        self.assertEqual(r.returncode,0,r.stderr)
        for field in ("slot=1","mac=aa:bb:cc:dd:ee:ff","enabled=1","runtime_verified=0"):
            self.assertIn(field,r.stdout)
        for kwargs,error in (({"OWNER":"other"},"foreign_acl_slot"),({"MAC":"bad"},"invalid_acl_mac"),({"ENABLED":"bad"},"invalid_acl_state")):
            self.assertIn(error,self.run_rpc("aclStatus",**kwargs).stdout)
    def test_stale_and_foreign_mutations_rejected_before_uci_write(self):
        import hashlib,json
        rev=hashlib.sha256((self.d/"firewall").read_bytes()).hexdigest()
        request=dict(revision=rev,slot="1",action="save",mac="aa:bb:cc:dd:ee:ff",enabled="1",confirmation="SAVE_LAN_ACL")
        for patch,env,error in (({"revision":"stale"},{},"stale_configuration"),({},{"OWNER":"foreign"},"foreign_acl_slot"),({"slot":"9"},{},"invalid_slot"),({"mac":"bad"},{},"invalid_mac")):
            r=self.run_rpc("saveAcl",json.dumps(request|patch),**env)
            self.assertIn(error,r.stdout,r.stderr)
            self.assertNotIn("MUTATION_ATTEMPT",r.stderr)
