'use strict';
const assert = require('node:assert/strict');
const {convert} = require('../enquota-adapter.js');
const evidence = {authoritative:true, authenticated:true, fetched_at:'2026-10-16T07:00:00Z'};
const item = {name:'Data utama',remainingBytes:1073741824,totalBytes:2147483648,
  validUntil:'2026-11-01T00:00:00+07:00'};
const valid = {success:true,provider:'XL',items:[item]};
assert.equal(convert(valid,evidence).state,'ok');
assert.equal(convert(valid,evidence).operator,'xl');
assert.equal(convert(valid,evidence).buckets[0].remaining_bytes,1073741824);
assert.equal(convert({...valid,provider:'AXIS'},evidence).operator,'axis');
assert.equal(convert({...valid,provider:'TRI'},evidence).operator,'tri');
assert.equal(convert(valid,null).state,'authentication_required');
assert.equal(convert(valid,{...evidence,authenticated:false}).buckets.length,0);
assert.equal(convert({...valid,success:false},evidence).state,'unavailable');
assert.equal(convert({...valid,items:[{...item,totalBytes:undefined}]},evidence).quality,'remaining_only');
assert.equal(convert({...valid,items:[{...item,remainingBytes:99999999999}]},evidence).state,'unavailable');
assert.equal(convert({...valid,items:[{...item,validUntil:'unknown'}]},evidence).state,'unavailable');
assert.equal(convert({...valid,items:[]},evidence).state,'unavailable');
assert.equal(convert({...valid,items:[{...item,remainingBytes:undefined,remainingMb:1024}]},evidence).state,'ok');

const remainingOnly = {success:true,provider:'XL',items:[{
  name:'XL Internet',type:'MAIN',remainingFormatted:'1.5 GB',validUntil:'-'
}]};
const partial = convert(remainingOnly,{...evidence,remaining_units_verified:true});
assert.equal(partial.state,'ok');
assert.equal(partial.quality,'remaining_only');
assert.equal(partial.buckets[0].remaining_bytes,1610612736);
assert.equal(Object.hasOwn(partial.buckets[0],'total_bytes'),false);
assert.equal(Object.hasOwn(partial.buckets[0],'expires_at'),false);
assert.equal(convert(remainingOnly,evidence).state,'unavailable');
assert.equal(convert({...remainingOnly,items:[{...remainingOnly.items[0],remainingFormatted:'unknown'}]},
  {...evidence,remaining_units_verified:true}).state,'unavailable');
assert.equal(convert({...remainingOnly,items:[{...remainingOnly.items[0],remainingFormatted:'0 MB of 10 GB'}]},
  {...evidence,remaining_units_verified:true}).state,'unavailable');
console.log('EnQuota-VeCI contract: remaining-only PASS');
