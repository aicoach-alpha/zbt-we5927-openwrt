'use strict';
const assert = require('node:assert/strict');
const {make} = require('../quota-manager.js');
const now = Date.parse('2026-10-16T07:00:00Z');
const m = make({
 xl: {
   capabilities: async()=>({state:'available', authentication:['otp','arbitrary']}),
   quota: async()=>({source:'operator',state:'ok',fetched_at:'2026-10-16T06:59:00Z',
     buckets:[{label:'Main',remaining_bytes:0,total_bytes:1024,expires_at:'2026-10-31T07:00:00Z'}]}),
   start_auth: async()=>({state:'pending_otp'}),
   complete_auth: async()=>({state:'authentication_required'})
 },
 axis: {
   capabilities: async()=>{throw Error('offline')},
   quota: async()=>{const e=Error('limited');e.code='rate_limited';throw e}
 }
},()=>now);
(async()=>{
 assert.equal((await m.quota('xl')).state,'ok');
 assert.equal((await m.quota('xl')).buckets[0].remaining_bytes,0);
 assert.equal((await m.quota('axis')).state,'rate_limited');
 assert.equal((await m.quota('telkomsel')).state,'not_supported');
 assert.deepEqual((await m.capabilities('xl')).authentication,['otp']);
 assert.equal((await m.capabilities('axis')).state,'unavailable');
 assert.equal((await m.startAuth('xl',{phone:'dummy'})).state,'pending_otp');
 assert.equal((await m.completeAuth('xl',{code:'dummy'})).state,'authentication_required');
 assert.equal((await m.refreshAuth('xl')).state,'not_supported');
 assert.equal((await m.logout('xl')).state,'not_supported');
 console.log('VeCI quota adapter manager: 10 tests PASS');
})().catch(e=>{console.error(e);process.exitCode=1});
