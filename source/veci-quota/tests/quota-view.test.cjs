'use strict';
const assert = require('node:assert/strict');
const {model} = require('../quota-view.js');
assert.equal(model(null).state, 'unavailable');
assert.equal(model({state:'authentication_required',buckets:[{remaining_bytes:123}]}).buckets.length,0);
assert.equal(model({state:'ok',source:'meter',buckets:[{remaining_bytes:123}]}).state,'unavailable');
assert.equal(model({state:'pending_otp'}).message,'Menunggu kode OTP');
const item = model({state:'ok',source:'operator',buckets:[{
  label:'Paket utama',remaining_bytes:1073741824,total_bytes:2147483648,
  expires_at:'2026-10-31T17:00:00Z'
}]});
assert.equal(item.state,'ok');
assert.equal(item.buckets[0].remaining,'1.00 GB');
assert.equal(item.buckets[0].total,'2.00 GB');
assert.equal(item.buckets[0].label,'Paket utama');
assert.equal(item.buckets.length,1);
console.log('VeCI quota view: 9 tests PASS');
