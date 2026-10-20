'use strict';
const assert = require('node:assert/strict');
const {model} = require('../quota-view.js');
const now = Date.parse('2026-10-20T09:00:00Z');
const stamp = '2026-10-20T08:59:00Z';
const full = {state:'ok',source:'operator',operator:'xl',fetched_at:stamp,
  buckets:[{label:'Paket utama',remaining_bytes:1073741824,total_bytes:2147483648,
    expires_at:'2026-10-31T17:00:00Z'}]};
assert.equal(model(null,now).state, 'unavailable');
assert.equal(model({state:'authentication_required',buckets:[{remaining_bytes:123}]},now).buckets.length,0);
assert.equal(model({...full,source:'meter'},now).state,'unavailable');
assert.equal(model({state:'pending_otp'},now).message,'Menunggu kode OTP');
const item = model(full,now);
assert.equal(item.state,'ok');
assert.equal(item.buckets[0].remaining,'1.00 GB');
assert.equal(item.buckets[0].total,'2.00 GB');
assert.equal(item.buckets[0].label,'Paket utama');
assert.equal(item.buckets.length,1);
const partial = model({...full,quality:'remaining_only',
  buckets:[{label:'XL Internet',remaining_bytes:1610612736}]},now);
assert.equal(partial.state,'ok');
assert.equal(partial.buckets[0].remaining,'1.50 GB');
assert.equal(Object.hasOwn(partial.buckets[0],'total'),false);
assert.equal(Object.hasOwn(partial.buckets[0],'expires'),false);
// Never display fabricated, nonnumeric, incomplete, or stale official quota.
assert.equal(model({...full,buckets:[]},now).state,'unavailable');
assert.equal(model({...full,buckets:[{label:'A',remaining_bytes:'0 MB'}]},now).state,'unavailable');
assert.equal(model({...full,buckets:[{label:'A',remaining_bytes:Infinity}]},now).state,'unavailable');
assert.equal(model({...full,buckets:[{label:'A',remaining_bytes:-1}]},now).state,'unavailable');
assert.equal(model({...full,buckets:[{label:'A',remaining_bytes:200,total_bytes:100,expires_at:'2026-11-01'}]},now).state,'unavailable');
assert.equal(model({...full,quality:undefined,buckets:[{label:'A',remaining_bytes:100}]},now).state,'unavailable');
assert.equal(model({...full,fetched_at:'2026-10-20T07:00:00Z'},now).state,'stale');
assert.equal(model({...full,fetched_at:'2026-10-20T10:00:00Z'},now).state,'stale');
assert.equal(model({...full,fetched_at:undefined},now).state,'stale');
assert.equal(model({...full,buckets:[full.buckets[0],{label:'bad',remaining_bytes:'NaN'}]},now).buckets.length,0);
console.log('VeCI quota-view targeted safety test PASS');
