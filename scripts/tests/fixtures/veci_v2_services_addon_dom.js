'use strict';
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');

function elt(id = '') {
  return {id, textContent:'', disabled:false, children:[], listeners:{},
    addEventListener(name, handler) { this.listeners[name]=handler; },
    replaceChildren(...nodes) { this.children=[...nodes]; },
    append(...nodes) { this.children.push(...nodes); },
    click() { this.listeners.click?.(); },
    };
}
async function flush() { for (let i=0;i<5;i++) await new Promise(resolve => setImmediate(resolve)); }
async function services(file) {
  const startup = new Map([
    ['startup-read', elt('startup-read')],
    ['startup-services', elt('startup-services')],
    ['startup-status', elt('startup-status')],
  ]);
  const requested = [], calls = [];
  const doc={getElementById(id) {requested.push(id); return startup.get(id)||null;},
    createElement: tag => elt(tag)};
  const ctx=vm.createContext({document:doc,sid:'test-session',window:{confirm:()=>true},
    rpc:async (name,method,args) => {
      calls.push([name,method,args]);
      assert.equal(name,'veci.v2.services');
      return {ok:true,services:[{name:'sysntpd',enabled:method==='save',mutable:true},
                                {name:'network',enabled:true,mutable:false}]};
    }});
  vm.runInContext(fs.readFileSync(file,'utf8'),ctx,{filename:file});
  assert.equal(typeof ctx.window.VeciServices.reset,'function');
  assert.equal(requested.includes('addon-read'),false);
  startup.get('startup-read').click();
  await flush();
  assert.equal(calls[0][1],'status');
  assert.equal(startup.get('startup-services').children.length,2);
  const active = startup.get('startup-services').children[0];
  assert.equal(active.children.length,1);
  active.children[0].click();
  await flush();
  assert.equal(calls[1][1],'save');
  assert.deepEqual(JSON.parse(JSON.stringify(calls[1][2])), {name:'sysntpd',expected:'0',enabled:'1'});
  ctx.window.VeciServices.reset();
  assert.equal(startup.get('startup-services').children.length,0);
}
async function addons(file) {
  const controls=new Map([
    ['addon-profiles-read',elt('addon-profiles-read')],
    ['addon-profiles-list',elt('addon-profiles-list')],
    ['addon-profiles-status',elt('addon-profiles-status')],
  ]);
  const calls=[];
  const ctx=vm.createContext({document:{
    getElementById: id => controls.get(id)||null,
    createElement: tag => elt(tag)},
    sid:'test-session',window:{confirm:()=>true},rpc:async (name,method,args) => {
      calls.push([name,method,args]);
      assert.equal(name,'veci.v2.addon');
      return {ok:true,wireguard:'disabled',guest:'disabled',voucher:'disabled'};
    }});
  vm.runInContext(fs.readFileSync(file,'utf8'),ctx,{filename:file});
  controls.get('addon-profiles-read').click();
  await flush();
  assert.equal(calls[0][1],'status');
  assert.equal(controls.get('addon-profiles-list').children.length,3);
  const wg=controls.get('addon-profiles-list').children[0];
  wg.children[0].click();
  await flush();
  assert.equal(calls[1][1],'setVpnStartup');
  assert.equal(calls[1][2].action,'ENABLE_WIREGUARD_NEXT_BOOT');
  assert.equal(calls[2][1],'status');
}
(async()=>{
  await services(process.argv[2]);
  await addons(process.argv[3]);
  console.log('PASS: canonical startup and addon DOM plus authenticated RPC state changes');
})().catch(error=>{console.error(error);process.exitCode=1});
