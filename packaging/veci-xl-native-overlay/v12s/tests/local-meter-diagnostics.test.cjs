'use strict';
// Focused v12s interaction contract: simulated DOM, local RPC only, zero OTP.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
class Element {
  constructor(tag,doc) { this.tag=tag; this.ownerDocument=doc; this.children=[]; this.textContent=''; this.hidden=false; this.disabled=false; this.value=''; this.listeners={}; }
  append(...items){this.children.push(...items);}
  replaceChildren(...items){this.children=items;}
  setAttribute(key,value){this[key]=value;}
  addEventListener(event,callback){this.listeners[event]=callback;}
}
const doc={createElement:tag=>new Element(tag,doc)};
const clipboard=[];
const navigator={clipboard:{writeText:async value=>clipboard.push(value)}};
const text=fs.readFileSync(path.join(__dirname,'../files/veci-xl-connection-status.js'),'utf8');
const mount=new Function('document','window','navigator',
  text.replace('export async function mountXlConnection','async function mountXlConnection')+
  ';return mountXlConnection;')(doc,{confirm:()=>true},navigator);
async function scenario(xl,meter,quota) {
  const host=new Element('host',doc), calls=[];
  await mount({querySelector:selector=>selector==='#veci-xl-connection'?host:null},{
    call:async(service,method)=>{
      calls.push(service+'.'+method);
      if(service==='veci.xl' && method==='status')return xl;
      if(service==='veci.meter' && method==='status') {
        if(meter instanceof Error)throw meter;
        return meter;
      }
      if(service==='veci.quota' && method==='status')return quota;
      throw Error('unexpected RPC');
    }
  });
  return {host,calls,controls:host.children[5],diagnostics:host.children[6],actions:host.children[7]};
}
(async()=>{
  const status={session:'not_connected',operator_configured:false,https_only:true};
  const x=await scenario(status,{state:'needs_baseline',carrier_authenticated:false},null);
  assert.equal(x.actions.hidden,true);
  assert.equal(x.calls.includes('veci.meter.status'),false);
  x.controls.children[3].listeners.click();
  assert.equal(x.actions.hidden,false);
  await x.actions.children[0].listeners.click();
  assert.equal(x.calls.filter(q=>q==='veci.meter.status').length,1);
  assert.match(x.diagnostics.textContent,/counter_lokal_sejak_boot/);
  assert.match(x.diagnostics.textContent,/bukan kuota operator/);
  await x.actions.children[1].listeners.click();
  assert.match(clipboard[0],/Diagnostik VeCI XL/);
  assert.doesNotMatch(clipboard[0],/access_token|OTP:|subscriber/i);
  const valid={provider:'xl',source:'operator',state:'ok',fetched_at:new Date().toISOString(),buckets:[
    {label:'Internet',remaining_bytes:100,total_bytes:200,expires_at:'2026-12-10T00:00:00Z'}]};
  const y=await scenario({...status,session:'verified',operator_configured:true},
    {state:'estimated',carrier_authenticated:false,traffic_since_baseline_bytes:999},valid);
  await y.actions.children[0].listeners.click();
  assert.match(y.diagnostics.textContent,/estimasi_lokal_bukan_sisa_kuota_operator/);
  assert.equal(y.host.children[0].textContent,'XL: kuota operator');
  const z=await scenario({...status,session:'private-id',access_token:'secret'},
    {state:'strange',carrier_authenticated:true,subscriber:'628123456789'},null);
  await z.actions.children[0].listeners.click();
  assert.match(z.diagnostics.textContent,/status_tidak_valid/);
  assert.doesNotMatch(z.diagnostics.textContent,/private-id|secret|628123456789/);
  const e=await scenario(status,Error('Bearer private-exception'),null);
  await e.actions.children[0].listeners.click();
  assert.match(e.diagnostics.textContent,/rpc_tidak_tersedia/);
  assert.doesNotMatch(e.diagnostics.textContent,/private-exception/);
  assert(![...x.calls,...y.calls,...z.calls,...e.calls].some(q=>q.endsWith('Otp')));
  console.log('XL_V12S_FOCUSED_UI=pass');
})().catch(e=>{console.error(e);process.exitCode=1;});
