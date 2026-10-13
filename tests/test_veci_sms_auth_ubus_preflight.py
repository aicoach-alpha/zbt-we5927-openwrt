"""SOURCE ONLY: mock rpcd ucode session ACL preflight, never call real router."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "source/we5927-lte/src/veci-sms-auth-ubus-preflight.uc"

HARNESS = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync(process.argv[1],'utf8');
let calls=[],code=0,serverAccess=true;
const fakeUbus={defer:(obj,fun,args,cb)=>{
    calls.push({obj,fun,args});
    cb(code,{access:serverAccess});
    return 'DEFERRED';
}};
const api=vm.runInNewContext('(function(){'+src+'})()', {
    require:(name)=>{
        assert.strictEqual(name,'ubus');
        return {connect:()=>fakeUbus};
    },
    type:(v)=>Number.isInteger(v)?'integer':(typeof v==='string'?'string':typeof v),
    match:(v,re)=>v.match(re),
});
const valid='a'.repeat(32);
function run(args,info) {
    let replies=[];
    let result=api['veci.sms.auth.audit'].probe.call({
        args,info,reply:(body,status)=>replies.push({body,status})
    });
    return {result,replies};
}
function req(sid=valid,more={}) {
    return {slot:4,scope:'authorization_preflight_only',
            ubus_rpc_session:sid,...more};
}
function context(more={}) {
    return {acl:{user:'root'},method:'probe',
            object:{name:'veci.sms.auth.audit'},...more};
}
let good=run(req(),context());
assert.strictEqual(good.result,'DEFERRED');
assert.deepStrictEqual(JSON.parse(JSON.stringify(good.replies[0].body)),
                       {ok:true,diagnostic_only:true});
assert.strictEqual(calls.length,1);
assert.strictEqual(calls[0].obj,'session');
assert.strictEqual(calls[0].fun,'access');
assert.deepStrictEqual(JSON.parse(JSON.stringify(calls[0].args)), {
    ubus_rpc_session:valid,scope:'ubus',
    object:'veci.sms.private',function:'readSlot'});
serverAccess=false;
let disallowed=run(req(),context());
assert.strictEqual(disallowed.replies[0].body.ok,false);
code=6;serverAccess=true;
assert.strictEqual(run(req(),context()).replies[0].body.ok,false);
code=0;serverAccess=true;
for(const test of [
    [req('0'.repeat(32)),context()],
    [req('BAD'),context()],
    [req(undefined,{slot:-1}),context()],
    [req(undefined,{slot:65536}),context()],
    [req(undefined,{scope:'readSlot'}),context()],
    [req(),context({acl:{user:'nobody'}})],
    [req(),context({acl:{user:'root'},method:'readSlot'})],
    [req(),context({acl:{user:'root'},object:{name:'veci.sms.private'}})],
    [req(),context({acl:{user:'guest'}})],
    [req(),{}]
]) {
    const before=calls.length;
    let r=run(test[0],test[1]);
    assert.strictEqual(r.result.reason,'not_authorized');
    assert.strictEqual(calls.length,before); // no ubus operation
}
console.log('VECI_UCODE_AUTH_MOCK_PASS');
"""

class UbusAuthPreflightTest(unittest.TestCase):
    def test_offline_ucode_contract(self):
        result = subprocess.run(["node","-e",HARNESS,str(SCRIPT)],
                                text=True,capture_output=True,timeout=12)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn("VECI_UCODE_AUTH_MOCK_PASS",result.stdout)

    def test_not_active_and_no_sensitive_operations(self):
        source=SCRIPT.read_text()
        self.assertIn("request.info",source)
        self.assertIn("acl.user",source)
        self.assertIn("ubus.defer('session', 'access'",source)
        self.assertNotIn("AT+CMGR=",source)
        self.assertNotIn("/dev/ttyUSB",source)
        self.assertNotIn("logger(",source)
        self.assertNotIn("console.log(",source)
        self.assertNotIn("sms.text",source)
        makefile=(ROOT/"source/we5927-lte/Makefile").read_text()
        self.assertNotIn("veci-sms-auth-ubus-preflight",makefile)
        self.assertFalse((ROOT/"source/we5927-lte/files/usr/share/rpcd/ucode/veci-sms-auth-ubus-preflight.uc").exists())

    def test_source_provenance_cannot_use_acl_user_as_browser_name(self):
        s=SCRIPT.read_text()
        self.assertIn("NOT the browser account name",s)
        self.assertIn("direct local ubus call can supply a claimed SID",s)
        self.assertNotIn("Number.isInteger",s)
        self.assertNotIn("typeof ",s)
        self.assertIn("type(args.slot) != 'integer'",s)
        self.assertNotIn("is_admin",s)
        self.assertNotIn("csrf_verified",s)
        self.assertNotIn("request.args.approved",s)

if __name__=="__main__":
    unittest.main()
