"""Single-process rpcd ucode SMS approval: mocked privilege and no modem/OTP."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
UC=ROOT/"source/we5927-lte/src/veci-sms-private-consent.uc"
ACL=ROOT/"source/we5927-lte/src/veci-sms-private-acl.json"

HARNESS=r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(process.argv[1],'utf8');
let instant=900000, authorized=true, entropy=true, accessCalls=[];
let randomCounter=7;
const ubus={
  defer:(o,m,a,cb)=>{
    accessCalls.push({o,m,a});
    cb(0,{access:authorized});
    return 'DEFERRED';
  }
};
const context={
  require:(name)=>{
    if(name==='ubus')return {connect:()=>ubus};
    if(name==='fs')return {readfile:(p,n)=>{
      assert.strictEqual(p,'/dev/urandom');
      assert.strictEqual(n,16);
      if(!entropy)return null;
      const bytes=Buffer.alloc(16,++randomCounter);
      return bytes.toString('latin1');
    }};
    throw Error('unexpected import '+name);
  },
  type:(v)=>{
    if(Array.isArray(v))return 'array';
    if(Number.isInteger(v))return 'integer';
    return typeof v;
  },
  match:(x,pattern)=>x.match(pattern),
  length:(x)=>x.length,
  int:(x)=>Math.trunc(x),
  hexenc:(x)=>Buffer.from(x,'latin1').toString('hex'),
  clock:(monotonic)=>{assert.strictEqual(monotonic,true);
    return [Math.floor(instant/1000),(instant%1000)*1000000];}
};
const api=vm.runInNewContext('(function(){'+source+'})()',context)['veci.sms.private'];
assert.deepStrictEqual(Object.keys(api).sort(),['armRead','readSlot']);
const good='a'.repeat(32), second='b'.repeat(32), anonymous='0'.repeat(32);
function request(method, args, peer='root') {
  let replies=[];
  let value=api[method].call({
    args:{...args,ubus_rpc_session:args.sid||good},
    info:{acl:{user:peer},object:{name:'veci.sms.private'},method},
    reply:(msg,rc)=>replies.push({msg,rc})
  });
  return replies.length?replies[0].msg:value;
}
const arm=(sid=good,slot=4,extras={})=>request('armRead',{
  sid,slot,scope:'single_sms_private_read',
  consent:'I_CONFIRM_READ_THIS_ONE_SMS',...extras
});
const read=(token,sid=good,slot=4,peer='root')=>
  request('readSlot',{sid,slot,token},peer);
let first=arm();
assert.strictEqual(first.ok,true);
assert.strictEqual(first.token.length,32);
assert.strictEqual(accessCalls.at(-1).a.function,'readSlot');
assert.strictEqual(arm().reason,'approval_pending');
assert.strictEqual(read(first.token).reason,'physical_read_disabled');
assert.strictEqual(read(first.token).reason,'approval_missing_or_expired');
let next=arm();
assert.notStrictEqual(next.token,first.token);
assert.strictEqual(read('f'.repeat(32)).reason,'not_authorized');
assert.strictEqual(read(next.token).reason,'approval_missing_or_expired');
// Cross-session mismatch burns nonce and never yields SMS.
let third=arm();
assert.strictEqual(read(third.token,second).reason,'not_authorized');
assert.strictEqual(read(third.token).reason,'approval_missing_or_expired');
// Permission from session.access cannot be bypassed by a valid SID.
authorized=false;
assert.strictEqual(arm().reason,'not_authorized');
authorized=true;
// Invalid/anonymous/unprivileged never touch ubus.
for(const [method,args,peer] of [
  ['armRead',{sid:anonymous,slot:4,scope:'single_sms_private_read',consent:'I_CONFIRM_READ_THIS_ONE_SMS'},'root'],
  ['armRead',{sid:good,slot:4,scope:'single_sms_private_read',consent:'I_CONFIRM_READ_THIS_ONE_SMS'},'nobody'],
  ['armRead',{sid:good,slot:65536,scope:'single_sms_private_read',consent:'I_CONFIRM_READ_THIS_ONE_SMS'},'root'],
  ['armRead',{sid:good,slot:4,scope:'single_sms_private_read',consent:'unconfirmed'},'root'],
  ['readSlot',{sid:good,slot:4,token:'garbage'},'root'],
  ['readSlot',{sid:good,slot:4,token:'0'.repeat(32)},'nobody']
]){
  const n=accessCalls.length;
  assert.strictEqual(request(method,args,peer).reason,'not_authorized');
  assert.strictEqual(accessCalls.length,n);
}
// Check monotonic expiry and no renewal without fresh consent.
let exp=arm();
instant+=30001;
assert.strictEqual(read(exp.token).reason,'approval_missing_or_expired');
assert.strictEqual(arm().ok,true);
instant-=40000;
assert.strictEqual(read('a'.repeat(32)).reason,'approval_missing_or_expired');
entropy=false;
assert.strictEqual(arm().reason,'unavailable');
assert.strictEqual(read('a'.repeat(32)).reason,'approval_missing_or_expired');
console.log('VECI_SINGLE_VM_CONSENT_PASS');
"""

class PrivateApproval(unittest.TestCase):
    def test_single_vm_two_step_consent_mock(self):
        run=subprocess.run(["node","-e",HARNESS,str(UC)],capture_output=True,
                           text=True,timeout=12)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertIn("VECI_SINGLE_VM_CONSENT_PASS",run.stdout)

    def test_source_only_and_no_sms_access(self):
        source=UC.read_text()
        for prohibited in ("AT+CMGR=","AT+CMGL=","/dev/ttyUSB",
                           "syslog(", "logger(", "console.log(",
                           "fs.writefile", "fs.popen", "fs.exec",
                           "request.args.is_admin","request.args.csrf_verified"):
            self.assertNotIn(prohibited,source)
        self.assertIn("pending = null",source)
        self.assertIn("clock(true)",source)
        self.assertIn("fs.readfile('/dev/urandom', 16)",source)
        self.assertIn("physical_read_disabled",source)
        fw=(ROOT/"source/we5927-lte/Makefile").read_text()
        self.assertNotIn("veci-sms-private-consent",fw)
        self.assertNotIn("veci-sms-private-acl",fw)
        self.assertFalse((ROOT/"source/we5927-lte/files/usr/share/rpcd/ucode/veci-sms-private-consent.uc").exists())

    def test_acl_never_public_and_separate_metadata(self):
        j=json.loads(ACL.read_text())
        self.assertEqual(len(j),1)
        rule=next(iter(j.values()))
        self.assertEqual(rule["read"]["ubus"],{})
        self.assertEqual(rule["write"]["ubus"]["veci.sms.private"],["armRead","readSlot"])
        self.assertNotIn("veci.sms",rule["write"]["ubus"])

if __name__=="__main__":
    unittest.main()
