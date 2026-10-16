'use strict';
const fs=require('fs'),assert=require('assert');
const js=fs.readFileSync('scripts/veci-sms-mifi-v15-staged/cellular.js','utf8');
const css=fs.readFileSync('scripts/veci-sms-mifi-v159-staged/sms-center.css','utf8');
assert(!js.includes('<style id="veci-sms-center-v158-styles">'),'inline style blocked by CSP');
assert(js.includes("link.href = '/veci/sms-center.css?v=159'"));
assert(js.includes("link.rel = 'stylesheet'"));
assert(js.includes("document.head.appendChild(link)"));
assert(css.includes('#cellular-sms-compose:not([hidden])'));
assert(css.includes('flex-direction: column !important;'));
assert(css.includes('label.sms-compose-field > textarea'));
assert(css.includes('flex-flow: column nowrap !important'));
assert(css.includes('#cellular-sms-compose[hidden]'));
for(const id of ['cellular-sms-compose','cellular-sms-to','cellular-sms-text','cellular-sms-send','cellular-sms-draft-save','cellular-sms-compose-close']){
  assert.strictEqual(js.split('id="'+id+'"').length-1,1,id);
}
for(const call of ["api.call('veci.sms','sendMessage'","api.call('veci.sms','saveDraft'","api.call('veci.sms','getSent'"]){
 assert(js.includes(call),'existing SMS feature must survive CSS migration: '+call);
}
console.log('VECI_SMS_V159_EXTERNAL_CSS_CSP_SMOKE_PASS');
