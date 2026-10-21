'use strict';
// One targeted owner-panel regression. No real router, OTP or operator network.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const moduleText = fs.readFileSync(path.join(__dirname, '../files/veci-xl-connection-status.js'),'utf8');
class E {
 constructor(tag,doc){this.tag=tag;this.ownerDocument=doc;this.children=[];this.textContent='';this.hidden=false;this.value='';this.listeners={};}
 append(...xs){this.children.push(...xs)}
 replaceChildren(...xs){this.children=xs}
 setAttribute(k,v){this[k]=v}
 addEventListener(event,handler){this.listeners[event]=handler}
}
const doc={createElement(tag){return new E(tag,doc)}};
const mount=new Function('document','window',moduleText.replace('export async function mountXlConnection','async function mountXlConnection')+';return mountXlConnection;')(doc,{confirm:()=>true});
async function inspect(status,quota) {
 const host=new E('div',doc),calls=[];
 await mount({querySelector:sel=>sel==='#veci-xl-connection'?host:null},{
   call:async(name,method)=>{
     calls.push(name+'.'+method);
     if(name==='veci.xl'&&method==='status')return status;
     if(name==='veci.quota'&&method==='status')return quota;
     throw Error('unexpected RPC');
   }
 });
 return {heading:host.children[0].textContent,details:host.children[1].textContent,
   quota:host.children[3].children.length,
   controls:host.children[5],diagnostic:host.children[6],calls};
}
(async()=>{
 const base={session:'not_connected',operator_configured:false,https_only:true};
 const pending=await inspect(base,null);
 assert.match(pending.diagnostic.textContent,/belum_tersedia/);
 assert.equal(pending.calls.includes('veci.quota.status'),false);
 assert.equal(pending.calls.some(x=>x.endsWith('requestOtp')),false);
 pending.controls.children[3].listeners.click();
 assert.equal(pending.diagnostic.hidden,false);
 const q={provider:'xl',source:'operator',state:'ok',fetched_at:new Date().toISOString(),
   buckets:[{label:'Internet',remaining_bytes:100,total_bytes:200,expires_at:'2026-11-15T00:00:00Z'}]};
 const verified=await inspect({...base,session:'verified',operator_configured:true},q);
 assert.equal(verified.heading,'XL: kuota operator');
 assert.match(verified.diagnostic.textContent,/terverifikasi_lengkap/);
 const invalid=await inspect({...base,session:'verified',operator_configured:true},{...q,source:'meter'});
 assert.notEqual(invalid.heading,'XL: kuota operator');
 assert.match(invalid.diagnostic.textContent,/tidak_tersedia/);
 const unknown=await inspect({...base,session:'private-session-secret',phone:'6285555555',access_token:'secret'},null);
 assert.match(unknown.diagnostic.textContent,/tidak_dikenal/);
 assert.doesNotMatch(unknown.diagnostic.textContent,/private-session-secret|6285555555|access_token|secret/);
 console.log('XL_V12R_DIAGNOSTICS_TEST=pass');
})().catch(e=>{console.error(e);process.exitCode=1});
