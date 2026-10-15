/* Pure offline LuCI contract tests, never calls router or operator. */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const base=path.join(root,'source/veci-telco-indonesia');
const src=fs.readFileSync(path.join(base,'files/www/luci-static/resources/view/veci/quota.js'),'utf8');
const menu=JSON.parse(fs.readFileSync(path.join(base,'files/usr/share/luci/menu.d/luci-app-veci-quota.json'),'utf8'));
const acl=JSON.parse(fs.readFileSync(path.join(base,'files/usr/share/rpcd/acl.d/veci-quota.json'),'utf8'));
const pkg=fs.readFileSync(path.join(base,'Makefile'),'utf8');
assert(menu['admin/network/veci_indonesia_quota']);
assert.equal(menu['admin/network/veci_indonesia_quota'].action.path,'veci/quota');
assert.deepEqual(menu['admin/network/veci_indonesia_quota'].depends.acl,['veci-quota']);
assert.deepEqual(acl['veci-quota'].read.ubus['veci.quota'],['status','providers']);
assert.equal(acl['veci-quota'].write,undefined);
assert(pkg.includes('www/luci-static/resources/view/veci/quota.js'));
assert(pkg.includes('luci-app-veci-quota.json'));
function make(status,providers,fail=false){
 const calls=[];
 const ctx={
  view:{extend:x=>x},
  rpc:{declare:arg=>{
   assert.equal(arg.object,'veci.quota');
   assert(['status','providers'].includes(arg.method));
   return async ()=>{
    calls.push(arg.method);
    if(fail)throw Error('mock_rpc_unavailable');
    return arg.method==='status'?status:{providers:providers};
   };
  }},
  ui:{createHandlerFn:(obj,fn)=>fn.bind(obj)},
  E:(tag,attr,children)=>({tag,attr,children:children||[]}),
  _:s=>s,Promise,String,Array,isFinite:Number.isFinite,
  document:{getElementById:()=>null}
 };
 const app=vm.runInNewContext(src,ctx);
 return {app,calls,async output(){return app.render(await app.load())}};
}
function flatten(n,items=[]){
 if(typeof n==='string'||typeof n==='number'){items.push(String(n));return items;}
 if(Array.isArray(n)){n.forEach(x=>flatten(x,items));return items;}
 if(n&&n.children)flatten(n.children,items);
 return items;
}
function find(n,tag,out=[]){
 if(Array.isArray(n))n.forEach(x=>find(x,tag,out));
 else if(n&&typeof n==='object'){
  if(n.tag===tag)out.push(n);
  find(n.children,tag,out);
 }
 return out;
}
const providers=[{id:'xl',name:'XL'},{id:'axis',name:'AXIS'},{id:'tri',name:'Tri'}];
const good={schema:1,provider:'xl',state:'ready',source:'carrier_authenticated',
 total_bytes:10737418240,remaining_bytes:5368709120,fetched_at:'2026-10-15T01:00:00Z'};
(async()=>{
 const test=make(good,providers);
 const rendered=await test.output();
 const text=flatten(rendered).join('\n');
 assert(text.includes('5.00 GB'));
 assert(text.includes('10.00 GB'));
 assert(text.includes('2026-10-15T01:00:00Z'));
 assert(text.includes('Verified carrier quota'));
 assert(text.includes('AXIS')&&text.includes('Tri'));
 const links=find(rendered,'a');
 assert.equal(links.length,1);
 assert(links[0].attr.href.startsWith('https://www.xl.co.id/'));
 assert.equal(links[0].attr.rel,'noopener noreferrer');
 assert.equal(test.app.handleSave,null);
 assert.equal(test.app.handleSaveApply,null);
 assert.deepEqual(test.calls.sort(),['providers','status']);
 for(const fake of [
  {...good,source:'parsed_only'},
  {...good,source:null},
  {...good,remaining_bytes:-1},
  {...good,remaining_bytes:3e10},
  {...good,state:'stale'},
  {...good,state:'not_connected'},
  {...good,total_bytes:'10737418240'},
  {...good,provider:'axis'}
 ]){
  const t=flatten(await make(fake,providers).output()).join('\n');
  assert(!t.includes('5.00 GB'),'unverified remaining quota leaked');
  assert(!t.includes('10.00 GB'),'unverified total quota leaked');
  assert(!t.includes('2026-10-15T01:00:00Z'));
 }
 const failtext=flatten(await make(null,[],true).output()).join('\n');
 assert(failtext.includes('Carrier quota unavailable'));
 assert(!failtext.includes('5.00 GB'));
 for(const forbidden of ['AT+CMGR','AT+CUSD','otpInput','access_token'])assert(!src.includes(forbidden));
 console.log('VECI_INDONESIA_QUOTA_LUCI_READONLY_PASS');
})().catch(e=>{console.error(e);process.exitCode=1;});
