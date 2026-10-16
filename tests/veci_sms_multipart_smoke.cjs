'use strict';
// Pure composition/decoding check: no modem, network, browser, SMS or user data.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync('scripts/veci-sms-mifi-v15-staged/cellular.js','utf8');
const a=src.indexOf('function buildSmsSubmit(');
const b=src.indexOf('function formatSmsDate(',a);
assert(a>=0&&b>a);
const {buildSmsSubmitSegments,decodeSentPdu}=
  vm.runInNewContext('(()=>{'+src.slice(a,b)+'return {buildSmsSubmitSegments,decodeSentPdu};})()');
const eq=(a,b,msg)=>assert.deepStrictEqual(JSON.parse(JSON.stringify(a)),b,msg);
function check(text,expectedParts,ref=27){
 const p=buildSmsSubmitSegments('+628123456789',text,ref);
 assert.strictEqual(p.length,expectedParts);
 const decoded=p.map((v,i)=>{
   const d=decodeSentPdu(v);
   assert.strictEqual(d.to,'+628123456789');
   if(expectedParts>1){
     assert.strictEqual(d.concat.ref,ref);
     assert.strictEqual(d.concat.total,expectedParts);
     assert.strictEqual(d.concat.part,i+1);
     assert.strictEqual(parseInt(v.slice(2,4),16),0x41);
     assert(v.includes('050003'));
   }else{
     assert.strictEqual(d.concat,null);
     assert.strictEqual(parseInt(v.slice(2,4),16),0x01);
   }
   return d.text;
 });
 assert.strictEqual(decoded.join(''),text,'multipart content round-trip');
 return p;
}
check('HELLO',1);
check('A'.repeat(160),1);
check('A'.repeat(161),2);
check('A'.repeat(307),3);
check('A'.repeat(610),4);
check('^'.repeat(85),2); // each ^ costs two GSM7 septets; no broken ESC.
check('{'.repeat(155),3);
check('你好'.repeat(35),1); // 70 UTF-16 units.
check('你好'.repeat(40),2);
check('😀'.repeat(50),2); // never split surrogate pair.
check('😀'.repeat(132),4);
assert.throws(()=>buildSmsSubmitSegments('+628123456789','😀'.repeat(134)),/four-part/);
assert.throws(()=>buildSmsSubmitSegments('+628123456789','A'.repeat(613)),/612/);
assert.throws(()=>buildSmsSubmitSegments('+628123456789','😀'.repeat(135)),/268/);
assert.throws(()=>buildSmsSubmitSegments('XLPRIORITAS','Hello'),/recipient/);
assert.throws(()=>buildSmsSubmitSegments('+628123456789','Hi',0),/reference/);
assert(src.includes('Do not automatically resend.'));
assert(src.includes('await new Promise(resolve=>setTimeout(resolve,5300))'));
assert(src.includes("api.call('veci.sms','sendMessage'"));
assert(src.includes("smsDraftSave.disabled=true"));
console.log('VECI_SMS_V160_MULTIPART_GSM7_UCS2_SEGMENTS_SENT_DECODER_PASS');
