/*
 * VeCI cafe Apps cards (v15).
 * Injected only into the authenticated Apps route by owning VeCI app.
 * No local credential storage, arbitrary packages, or fake install success.
 */
import {VECI_CAFE_CATALOG, VECI_CAFE_CATEGORIES, cafeEssentials} from './veci-cafe-app-catalog.js';
function el(doc,tag,cls,text){
 const node=doc.createElement(tag);
 if(cls) node.className=cls;
 if(text!==undefined) node.textContent=text;
 return node;
}
export function renderCafeApps(root,{service=null,doc=root.ownerDocument,showAdvanced=false}={}){
 if(!root || !doc || !doc.createElement) throw new TypeError('Apps root required');
 const chosen=showAdvanced?VECI_CAFE_CATALOG:cafeEssentials();
 const outer=el(doc,'section','veci-cafe-apps');
 const head=el(doc,'div','veci-cafe-apps-intro');
 head.append(el(doc,'h2','','Apps untuk Kafe & Router'));
 head.append(el(doc,'p','',
  'Voucher, bandwidth, keamanan tamu dan monitoring. Status instalasi dibaca dari router, bukan perkiraan.'));
 outer.append(head);
 const notice=el(doc,'p','veci-cafe-apps-note',
  'Khusus perangkat ini, instalasi paket diblokir jika tidak muat atau tidak tersedia di feed firmware. Hotspot voucher memerlukan portal dan backend voucher yang benar; kode voucher belum aktif.');
 outer.append(notice);
 const controls=new Map();
 for(const category of VECI_CAFE_CATEGORIES){
  const group=el(doc,'section','veci-cafe-apps-category');
  group.append(el(doc,'h3','',category));
  const grid=el(doc,'div','veci-cafe-apps-grid');
  for(const item of chosen.filter(x=>x.category===category)){
   const card=el(doc,'article','veci-cafe-card');
   card.dataset.appId=item.id;
   card.append(el(doc,'h4','',item.title));
   card.append(el(doc,'p','veci-cafe-card-description',item.description));
   const status=el(doc,'div','veci-cafe-card-status',
    item.mode==='builtin'?'Fitur bawaan':item.mode==='development'?'Perlu integrasi':'Memeriksa paket resmi…');
   status.setAttribute('role','status');
   card.append(status);
   const foot=el(doc,'div','veci-cafe-card-footer');
   foot.append(el(doc,'span','veci-cafe-card-priority',item.priority));
   if(item.mode==='builtin'){
    const anchor=el(doc,'a','veci-cafe-card-link','Buka');
    anchor.href=item.route;
    foot.append(anchor);
   }else if(item.mode==='optional'){
    const button=el(doc,'button','veci-cafe-card-button','Periksa paket');
    button.type='button';
    button.disabled=true;
    foot.append(button);
    controls.set(item.id,{item,button,status});
   }
   card.append(foot);
   grid.append(card);
  }
  group.append(grid);
  outer.append(group);
 }
 root.replaceChildren(outer);
 const refresh=async()=>{
  if(!service || typeof service.inventory!=='function'){
   for(const c of controls.values())c.status.textContent='Pengelola paket belum terhubung';
   return;
  }
  let inventory;
  try { inventory=await service.inventory(true); }
  catch {
   for(const c of controls.values()){
    c.button.disabled=true;
    c.button.textContent='Tidak tersedia';
    c.status.textContent='Gagal membaca status paket';
   }
   return;
  }
  for(const {item,button,status} of controls.values()){
   const record=inventory.apps?.[item.id];
   const hasPackage=record && record.package===item.package;
   const operation=inventory.operation;
   const busy=operation?.state==='running'||operation?.state==='queued';
   const installed=Boolean(record?.installed);
   if(!hasPackage) status.textContent='Paket belum terdaftar dalam backend';
   else if(installed)status.textContent='Terpasang: '+item.package;
   else if(!inventory.feedConfigured)status.textContent='Feed resmi belum dikonfigurasi';
   else if(!record.available)status.textContent='Paket tidak ada pada feed yang terhubung';
   else if(Number(inventory.freeOverlayKiB)<8192)status.textContent='Flash tidak cukup untuk instalasi aman';
   else status.textContent='Tersedia di feed · periksa dependensi';
   const available=Boolean(hasPackage && !busy &&
      (installed || (inventory.feedConfigured && record.available && Number(inventory.freeOverlayKiB)>=8192)));
   button.disabled=!available;
   button.textContent=busy?'Sedang diproses':installed?'Uninstall':'Install';
   button.onclick=async()=>{
    if(!available || typeof service.action!=='function')return;
    const action=installed?'uninstall':'install';
    const text=(action==='install'?'Pasang ':'Hapus ')+item.title+'? Perubahan paket dapat memengaruhi koneksi.';
    if(doc.defaultView?.confirm?.(text)!==true)return;
    button.disabled=true;
    button.textContent='Memproses…';
    try {
      const result=await service.action(item.title,action);
      status.textContent=result?.accepted?'Permintaan diterima, bukan konfirmasi instalasi.':'Permintaan ditolak';
    }catch{status.textContent='Operasi gagal; periksa status paket.';}
    await refresh();
   };
  }
 };
 void refresh();
 return {count:chosen.length,refresh,dispose:()=>root.replaceChildren()};
}
