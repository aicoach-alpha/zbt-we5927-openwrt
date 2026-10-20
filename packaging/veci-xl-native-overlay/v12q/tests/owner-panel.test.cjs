'use strict';
// Targeted integration test: owner UI + operator quota guard (no real network/OTP).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
class Elem {
  constructor(tag) {
    this.tag=tag; this.children=[]; this.textContent=''; this.hidden=false;
    this.disabled=false; this.value=''; this.ownerDocument=doc;
    this.listeners={};
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children=[...children]; }
  setAttribute(k,v) { this[k]=v; }
  addEventListener(name,cb){ this.listeners[name]=cb; }
}
const doc={createElement:(tag)=>new Elem(tag)};
global.document=doc;
global.window={confirm:()=>true};
async function run(mount, quotaData, statusOverride) {
  const host = new Elem('div');
  const root = {querySelector: selector => selector==='#veci-xl-connection'?host:null};
  const calls=[];
  const status={session:'verified',operator_configured:true,https_only:true,...statusOverride};
  const api={call:async (service,method) => {
    calls.push([service,method]);
    if(service==='veci.xl' && method==='status') return status;
    if(service==='veci.quota' && method==='status') return quotaData;
    throw Error('unexpected api call');
  }};
  await mount(root,api);
  // append order: heading, details, official, quota, login, controls
  return {heading:host.children[0].textContent, details:host.children[1].textContent,
    items:host.children[3].children,calls};
}
(async()=>{
  const file=path.join(__dirname,'..','files','veci-xl-connection-status.js');
  const js=fs.readFileSync(file,'utf8');
  const {mountXlConnection}=await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));
  const now=new Date().toISOString();
  const full={provider:'xl',state:'ok',source:'operator',fetched_at:now,
    buckets:[{label:'Internet utama',remaining_bytes:1048576,total_bytes:2097152,expires_at:'2026-12-31T23:00:00Z'}]};
  let out=await run(mountXlConnection,full);
  assert.equal(out.heading,'XL: kuota operator');
  assert.equal(out.items.length,1);
  out=await run(mountXlConnection,{...full,quality:'remaining_only',
    buckets:[{label:'Data resmi',remaining_bytes:1048576}]});
  assert.equal(out.heading,'XL: kuota operator');
  assert.equal(out.items.length,1);
  for (const bad of [
    {...full,buckets:[{label:'Sisa',remaining_bytes:1}]},
    {...full,quality:'fake_complete',buckets:[{label:'Sisa',remaining_bytes:1}]},
    {...full,buckets:[{label:'Sisa',remaining_bytes:'2 GB'}]},
    {...full,buckets:[{label:'Sisa',remaining_bytes:-1}]},
    {...full,buckets:[]},
    {...full,buckets:[{label:'Sisa',remaining_bytes:5,total_bytes:3,expires_at:'2026-12-01'}]},
    {...full,source:'meter'},
    {...full,fetched_at:new Date(Date.now()-3600001).toISOString()}
  ]) {
    out=await run(mountXlConnection,bad);
    assert.notEqual(out.heading,'XL: kuota operator');
    assert.equal(out.items.length,0);
  }
  out=await run(mountXlConnection,full,{operator_configured:false,session:'not_connected'});
  assert.equal(out.heading,'XL: konfigurasi operator belum tersedia');
  assert.equal(out.calls.filter(x=>x[0]==='veci.quota').length,0);
  console.log('XL_V12Q_UI_TEST=pass');
})().catch(e=>{console.error(e);process.exitCode=1});
