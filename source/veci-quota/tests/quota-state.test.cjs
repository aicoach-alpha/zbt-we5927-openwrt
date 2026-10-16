'use strict';
const assert = require('node:assert/strict');
const {normalize} = require('../quota-state.js');
const now = Date.parse('2026-10-16T07:00:00Z');
const valid = {operator:'xl',source:'operator',state:'ok',fetched_at:'2026-10-16T06:59:00Z',
  buckets:[{label:'Internet utama',remaining_bytes:0,total_bytes:1048576,expires_at:'2026-10-31T17:00:00Z'}]};
assert.equal(normalize(valid,now).state,'ok');
assert.equal(normalize(valid,now).buckets[0].remaining_bytes,0);
assert.equal(normalize({...valid,source:'meter'},now).state,'unavailable');
assert.equal(normalize({...valid,buckets:[{...valid.buckets[0],remaining_bytes:-1}]},now).state,'unavailable');
assert.equal(normalize({...valid,buckets:[{...valid.buckets[0],remaining_bytes:1048577}]},now).state,'unavailable');
assert.equal(normalize({...valid,fetched_at:'2026-10-16T05:00:00Z'},now).state,'stale');
assert.equal(normalize({...valid,fetched_at:'2026-10-16T08:00:00Z'},now).state,'stale');
assert.equal(normalize({state:'authentication_required',operator:'xl',buckets:valid.buckets},now).buckets.length,0);
assert.equal(normalize(null,now).state,'unavailable');
assert.equal(normalize({...valid,buckets:[]},now).state,'unavailable');
assert.equal(normalize({...valid,buckets:[{...valid.buckets[0],total_bytes:NaN}]},now).state,'unavailable');
console.log('VeCI quota normalizer: 11 tests PASS');