'use strict';
// Sent Messages decode regression, no real SMS or AT commands.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('scripts/veci-sms-mifi-v15-staged/cellular.js','utf8');
const a=source.indexOf('function decodeSentPdu('),b=source.indexOf('function formatSmsDate(',a);
assert(a>=0&&b>a,'No Sent decoder');
const decode=vm.runInNewContext('(()=>{'+source.slice(a,b)+';return decodeSentPdu})()');
const good='0001000B912143658709F1000005C82293F904';
assert.strictEqual(decode(good).recipient,'+12345678901');
assert.strictEqual(decode(good).message,'HELLO');
assert.throws(()=>decode('AT+CMGS=18'),/Invalid sent record/);
assert.throws(()=>decode(good.slice(0,-2)),/Invalid GSM7/);
const unicode='0001000B912143658709F100080400480049';
assert.strictEqual(decode(unicode).message,'HI');
assert(source.includes("api.call('veci.sms','getSent'"));
assert(source.includes("smsSentPanel.hidden=true"));
assert(source.includes("r.history_saved===false"));
console.log('VECI_SENT_SMS_DECODE_AND_PRIVACY_SMOKE_PASS');
