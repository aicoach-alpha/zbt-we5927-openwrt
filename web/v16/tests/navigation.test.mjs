import test from 'node:test';
import assert from 'node:assert/strict';
import {planMenu, GROUPS, FEATURES} from '../veci-lean-navigation.mjs';
const base = [
  '#/home','#/internet','#/cellular','#/wi-fi','#/devices',
  '#/network','#/security','#/system','#/apps'
].map(href => ({href}));

test('six compact groups preserve all verified feature routes', () => {
  const p = planMenu(base);
  assert.equal(p.ok, true);
  assert.deepEqual(p.groups.map(g=>g.id), ['home','internet','wifi','devices','settings','apps']);
  assert.equal(p.count, 9);
  assert.equal(p.hasOta, false);
});
test('OTA appears once and ONLY inside Settings, with verified source route',()=>{
  const p=planMenu([...base,{href:'#/firmware'},{href:'#/update'},{href:'#/update'}]);
  assert.equal(p.ok,true);
  const ota=p.groups.flatMap(g=>g.items).filter(x=>x.id==='ota');
  assert.equal(ota.length,1);
  assert.equal(ota[0].href,'#/update');
  assert.equal(p.groups.find(g=>g.id==='settings').items.filter(x=>x.id==='ota').length,1);
  assert.equal(p.groups.filter(g=>g.id!=='settings').flatMap(g=>g.items).filter(x=>x.id==='ota').length,0);
});
test('missing required route fails closed instead of fabricating a page',()=>{
  const p=planMenu(base.filter(x=>x.href!=='#/network'));
  assert.equal(p.ok,false);
  assert.deepEqual(p.missing,['network']);
  assert.equal(p.groups.length,0);
});
test('duplicate route inventory cannot create duplicate menus',()=>{
  const p=planMenu([...base,...base,{href:'#/update'}]);
  assert.equal(p.ok,true);
  assert.equal(p.count,10);
  assert.equal(new Set(p.groups.flatMap(g=>g.items.map(i=>i.href))).size,10);
});
test('malformed routes do not create navigation entries',()=>{
  const p=planMenu([...base,{href:'javascript:alert(1)'},{href:'#/update\nmalicious'}]);
  assert.equal(p.ok,true);
  assert.equal(p.hasOta,false);
});
test('all route IDs and canonical owners are unique',()=>{
  assert.equal(new Set(FEATURES.map(f=>f.id)).size,FEATURES.length);
  assert.equal(new Set(GROUPS.flatMap(g=>g.features)).size,FEATURES.length);
});
