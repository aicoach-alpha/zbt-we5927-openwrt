'use strict';
// One PDU contract check for Compose SMS, numeric Reply and GSM7/UCS2.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync('scripts/veci-sms-mifi-v15-staged/cellular.js','utf8');
const start=src.indexOf('function buildSmsSubmit(');
const end=src.indexOf('function formatSmsDate(',start);
assert(start>=0 && end>start);
const build=vm.runInNewContext('(()=>{'+src.slice(start,end)+';return buildSmsSubmit;})()');
const g=build('+628123456789','HELLO');
assert(g.startsWith('0001000C91'));
assert(g.endsWith('000005C82293F904'),g);
const e=build('628123456789','ABC');
assert(e.startsWith('0001000C81'));
const u=build('+628123456789','😀');
assert(u.includes('000808D83DDE00')); // PID, UCS2 DCS, 4 UTF-16 octets
assert.throws(()=>build('+628123456789','a'.repeat(161)),/limit|fit/);
assert.throws(()=>build('XLPRIORITAS','HELLO'),/recipient/);
assert.throws(()=>build('+628123456789','😀'.repeat(36)),/Unicode/);
assert(src.includes("api.call('veci.sms','sendMessage'"));
assert(src.includes("smsCompose.addEventListener('submit'"));
console.log('VECI_SMS_COMPOSE_GSM7_UCS2_NO_AUTOSEND_PASS');
