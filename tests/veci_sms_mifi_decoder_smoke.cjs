// One short release regression for real-world operator alphanumeric SMS PDU.
// Synthetic fixture ONLY; no real sender, messages, modem or credentials.
'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync('scripts/veci-sms-mifi-v15-staged/cellular.js','utf8');
const begin=src.indexOf('function decodePrivatePdu(');
const end=src.indexOf('\nexport default',begin);
assert(begin>=0&&end>begin);
const decode=vm.runInNewContext('(()=>{'+src.slice(begin,end)+'; return decodePrivatePdu})()',{Uint8Array,String,Math,Number,Error});
function p7(s){let a=Array(Math.ceil(s.length*7/8)).fill(0);for(let i=0;i<s.length;i++){let code=s.charCodeAt(i)&127;for(let b=0;b<7;b++){if(code&(1<<b)){let off=i*7+b;a[off>>3]|=1<<(off&7)}}}return a}
function hex(a){return a.map(n=>n.toString(16).padStart(2,'0')).join('').toUpperCase()}
function pdu(sender,body,dcs){return hex([0,4,Math.ceil(sender.length*7/4),208,...p7(sender),0,dcs,0,0,0,0,0,0,0,body.length,...p7(body)])}
for(const [who,msg,dcs] of [['XL','HELLO',0],['TELKOMSEL','TEST',241],['BANK','OK',192],['BYU','HI',208]]){
  const dec=decode(pdu(who,msg,dcs));
  assert.strictEqual(dec.sender,who);assert.strictEqual(dec.text,msg);
}
const numeric='00040B912143658709F100000000000000000005C82293F904';
const ucs2='00040B912143658709F10008000000000000000400480049';
assert.strictEqual(decode(numeric).text,'HELLO');
assert.strictEqual(decode(ucs2).text,'HI');
assert.throws(()=>decode(numeric.slice(0,-4)),/size|truncated/);
assert(!src.includes("console.log(item.pdu)"));
console.log('VECI_MIFI_SMS_OPERATOR_ALPHA_DCS_SMOKE_PASS');
