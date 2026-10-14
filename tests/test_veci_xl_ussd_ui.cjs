/* Test the XL menu is a pure overlay of the known-good v1.6.0 SMS UI. */
'use strict';
const fs=require('node:fs');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const path=require('node:path');
const root=path.join(__dirname,'..');
const original=fs.readFileSync(path.join(root,'scripts/veci-sms-mifi-v15-staged/cellular.js'),'utf8');
let actual=fs.readFileSync(path.join(root,'scripts/veci-xl-ussd-v17-staged/cellular-v160.js'),'utf8');
function removeBetween(begin,end){
 const a=actual.indexOf(begin),b=actual.indexOf(end,a);
 assert(a>=0&&b>a,begin);
 const block=actual.slice(a,b);
 actual=actual.slice(0,a)+actual.slice(b);
 return block;
}
const helper=removeBetween('/* XL official *808#;','/* Decode only locally-saved,');
const html=removeBetween('\t\t\t<section class="notice-card" id="cellular-xl-ussd">',
                         '\t\t\t<div class="notice-card">\n\t\t\t\t<strong>Hardware-aware integration');
const logic=removeBetween('\t\t// XL USSD is a separate write-ACL feature',
                          "\t\tconst reconnect = root.querySelector('#cellular-reconnect');");
assert.equal(actual,original,'All non-USSD SMS UI bytes must equal LIVE v1.6.0 baseline');
assert(!actual.includes('requestSmsDeliveryReport('));
const context={};
vm.runInNewContext(helper+'globalThis.parse=parseXlUssdQuota;',context);
const parse=context.parse;
for(const [t,expected] of [
 ['Sisa Kuota: 1,5 GB','1,5 GB'],
 ['XL: Sisa Paket Internet 250 MB','250 MB'],
 ['SISA KUOTA - 1024 KB','1024 KB'],
 ['Kuota awal 20 GB',null],
 ['Aktifkan kuota 9 GB',null],
 ['Beli 5 GB dengan Rp 50.000',null],
 ['Sisa kuota tidak diketahui',null],
 ['Sisa kuota 999999 GB',null],
 ['Sisa kuota 1,234567 GB',null]
]){
 assert.equal(parse(t),expected,t);
}
assert(html.includes('cellular-xl-ussd-start'));
assert(html.includes('cellular-xl-quota'));
for(const fragment of ["api.call('veci.ussd','start'","api.call('veci.ussd','reply'",
                       "api.call('veci.ussd','cancel'","I_APPROVE_THIS_USSD_CHOICE"]){
 assert(logic.includes(fragment),fragment);
}
assert(!logic.includes('localStorage'));
console.log('VECI_XL_USSD_UI_ON_V160_BASELINE_PASS');
