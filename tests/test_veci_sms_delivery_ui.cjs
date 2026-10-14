/* Offline v1.6.1 UI contract: no browser, real router or SMS sending. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const file=path.join(__dirname,'../scripts/veci-sms-delivery-v161-staged/cellular.js');
let source=fs.readFileSync(file,'utf8');
assert(source.startsWith("import { badge, escapeHtml, setBusy } from '../lib/dom.js';"));
source=source.replace(/^import \{ badge, escapeHtml, setBusy \} from '\.\.\/lib\/dom\.js';\r?\n/,'');
source=source.replace('export default {','const page = {');
source+='\nglobalThis.contract={requestSmsDeliveryReport,buildSmsSubmitSegments,decodeSentPdu};';
const context={Uint8Array,Math,Map,Number,Object,String,Error,console,globalThis:{}};
vm.runInNewContext(source,context,{timeout:2000,filename:'veci-v161-ui'});
const {requestSmsDeliveryReport:request,buildSmsSubmitSegments:build,decodeSentPdu:decode}=context.globalThis.contract;
for(const pair of [
  {message:'Hello VeCI',expected:1},
  {message:'X'.repeat(325),expected:3},
  {message:'Halo 😊',expected:1},
  {message:'😊'.repeat(80),expected:3}
]){
  const original=build('+628123456789',pair.message,17);
  assert.equal(original.length,pair.expected);
  const converted=original.map(request);
  converted.forEach((pdu,i)=>{
    const before=original[i].slice(2,4),after=pdu.slice(2,4);
    assert.equal(after,before==='01'?'21':'61');
    assert.equal(pdu.slice(4),original[i].slice(4));
    assert.equal(pdu.length,original[i].length);
    const decoded=decode(pdu);
    assert.equal(decoded.to,'+628123456789');
    if(pair.expected>1){
      assert.equal(decoded.concat.total,pair.expected);
      assert.equal(decoded.concat.part,i+1);
    }
  });
  assert.equal(converted.map(p=>decode(p).text).join(''),pair.message);
}
for(const invalid of [
  'AT+CMGD=1','', '0021000B912143658709F1000005C82293F904',
  '0021'+'00'.repeat(192),
]){
  assert.throws(()=>request(invalid));
}
assert(source.includes('Delivered (operator report)'));
assert(source.includes('Delivery unconfirmed'));
assert(source.includes('trackingMissing'));
console.log('VECI_V161_UI_DELIVERY_REPORT_OFFLINE_PASS');
