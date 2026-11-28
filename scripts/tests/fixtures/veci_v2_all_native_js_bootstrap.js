'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const assert=require('node:assert/strict');
const html=fs.readFileSync(process.argv[2],'utf8');
const dir=path.dirname(process.argv[2]);
const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(x=>x[1]);
const elements=new Map();
const missing=[];
const fakeClass=()=>({add(){},remove(){},contains(){return false},toggle(){return true}});
function make(id) {
  return {id,tagName:'DIV',value:'',textContent:'',innerText:'',hidden:false,
    disabled:false,checked:false,style:{},dataset:{},classList:fakeClass(),
    children:[],options:[],listeners:{},files:[],clientWidth:100,
    addEventListener(event,fn){this.listeners[event]=fn},
    setAttribute(){},getAttribute(){return null},removeAttribute(){},
    replaceChildren(...children){this.children=[...children]},
    append(...nodes){this.children.push(...nodes)},
    appendChild(node){this.children.push(node);return node},
    replaceWith(){}, remove(){},reset(){},blur(){},focus(){},
    querySelector(){return null},querySelectorAll(){return []},closest(){return null},
    getContext(){return {clearRect(){},fillRect(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},fillText(){},measureText(){return {width:10}}}},
    scrollIntoView(){},getBoundingClientRect(){return {width:100,height:100,left:0,top:0}},
  };
}
for(const id of ids)elements.set(id,make(id));
const badFields=[];
for(const id of ids){
  const start=html.indexOf('<form id="'+id+'"');
  if(start<0)continue;
  const end=html.indexOf('</form>',start);
  if(end<0)continue;
  const fragment=html.slice(start,end);
  const names=[...fragment.matchAll(/<(?:input|select|textarea|fieldset)[^>]*\bname="([^"]+)"/g)].map(x=>x[1]);
  const group=Object.fromEntries(names.map(name=>[name,make(id+'.'+name)]));
  elements.get(id).elements=new Proxy(group,{get(obj,field) {
    if(typeof field==='symbol')return undefined;
    if(!(field in obj)){badFields.push(id+'.'+field);return undefined;}
    return obj[field];
  }});
}
const listeners={};
const doc={
  body:make('body'),
  getElementById(id){if(!elements.has(id)){missing.push(id);return null;}return elements.get(id)},
  createElement:tag=>make(tag),
  querySelector(){return null},
  querySelectorAll(){return []},
  addEventListener(name,fn){listeners[name]=fn}
};
const ctx=vm.createContext({
  document:doc,console,setTimeout,clearTimeout,AbortController,
  TextDecoder,TextEncoder,URL,Uint8Array,DataView,Blob,Buffer,
  navigator:{},location:{protocol:'https:',hostname:'router',reload(){}},
  fetch:async()=>({ok:true,json:async()=>({result:[0,{}]})}),
  confirm:()=>true,alert(){},FileReader:class{addEventListener(){}},
  Option:class{constructor(label,value){this.label=label;this.value=value}},
  screen:{width:1200},
});
ctx.window=ctx;
const ordered=[...html.matchAll(/<script[^>]+src="\/veci2\/([^"]+\.js)"[^>]*><\/script>/g)].map(x=>x[1]);
assert(ordered.length>=15,'missing native script source list');
for(const file of ordered){
  const contents=fs.readFileSync(path.join(dir,file),'utf8');
  try{vm.runInContext(contents,ctx,{filename:file,timeout:2200});}
  catch(error){console.error('BOOTSTRAP_MODULE_ERROR',file,String(error.stack||error));process.exitCode=1;break}
}
console.log('SCRIPTS_BOOTSTRAPPED',ordered.length,'MISSING_STATIC_DOM_IDS',JSON.stringify([...new Set(missing)]),
  'MISSING_FORM_FIELDS',JSON.stringify([...new Set(badFields)]));
if(missing.length){console.error('Missing frontend IDs when loading native modules:',missing);process.exitCode=1}
if(badFields.length){console.error('Missing form fields in native modules:',badFields);process.exitCode=1}
if(!ctx.VeciServices||!ctx.VeciAddonProfiles){console.error('Missing canonical UI managers');process.exitCode=1}
