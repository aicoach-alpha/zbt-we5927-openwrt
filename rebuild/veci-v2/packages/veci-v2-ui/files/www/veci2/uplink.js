'use strict';
(() => {
  const el=id=>document.getElementById(id), b=el('uplink-refresh'), result=el('uplink-result');
  if(!b||!result)return;
  let profile=null,busy=false;
  function reset(){
    profile=null;el('uplink-form').reset();
    for(const id of ['uplink-provision','uplink-save','uplink-toggle'])el(id).disabled=true;
    result.textContent='';
  }
  async function perform(method,args,success,accept){
    const token=sid;if(!token||busy)return;
    busy=true;b.disabled=true;reset();
    try{
      const r=await rpc('veci.v2.wifi',method,args,token,25000);
      if(!r.ok||!accept(r))throw Error(r.error||'Perubahan belum terkonfirmasi');
      if(sid===token)result.textContent=success;
    }catch(e){if(sid===token)result.textContent=e.message;}
    finally{if('password' in args)args.password='';busy=false;b.disabled=false;}
  }
  b.onclick=async()=>{
    const token=sid;if(!token||busy)return;
    busy=true;b.disabled=true;reset();
    try{
      const x=await rpc('veci.v2.wifi','uplinkStatus',{},token,20000);
      if(!x.ok||!/^[0-9a-f]{64}$/.test(x.revision||''))throw Error(x.error||'Status tidak tersedia');
      if(sid!==token)return;
      profile=x;el('uplink-ssid').value=x.ssid||'';
      result.textContent=x.eligible?'WWAN tersedia; koneksi belum terverifikasi.':x.provisionable?'WWAN belum dibuat.':'Topologi tidak kompatibel.';
      el('uplink-provision').disabled=!x.provisionable;
      el('uplink-save').disabled=!x.eligible||x.enabled;
      el('uplink-toggle').disabled=!x.eligible||!x.configured;
      el('uplink-toggle').textContent=x.enabled?'Nonaktifkan pada boot berikutnya':'Aktifkan pada boot berikutnya';
    }catch(e){if(sid===token)result.textContent=e.message;}
    finally{busy=false;b.disabled=false;}
  };
  el('uplink-provision').onclick=()=>{
    const x=profile;if(!x||!x.provisionable||location.protocol!=='https:')return;
    if(!window.confirm('Siapkan WWAN DHCP IPv4 tanpa mengaktifkan STA?'))return;
    perform('provisionWwan',{revision:x.revision,confirmation:'PROVISION_WWAN_DISABLED'},'WWAN disiapkan. Baca status sebelum membuat profil.',r=>r.eligible===true&&r.enabled===false&&r.configured===false);
  };
  el('uplink-form').onsubmit=e=>{
    e.preventDefault();const x=profile;if(!x||!x.eligible||x.enabled||location.protocol!=='https:')return;
    if(!window.confirm('Simpan profil WPA2 dalam keadaan nonaktif?'))return;
    perform('saveUplink',{revision:x.revision,action:'save',confirmation:'SAVE_UPLINK_DISABLED',ssid:el('uplink-ssid').value,password:el('uplink-secret').value},'Profil nonaktif disimpan. Baca status sebelum mengaktifkan.',r=>r.configured===true&&r.enabled===false);
  };
  el('uplink-toggle').onclick=()=>{
    const x=profile;if(!x||!x.eligible||!x.configured||location.protocol!=='https:')return;
    const enable=!x.enabled;
    if(!window.confirm('Ubah startup uplink? Aktivasi manual dapat memengaruhi Wi-Fi utama.'))return;
    perform('saveUplink',{revision:x.revision,action:enable?'enable':'disable',confirmation:enable?'ENABLE_UPLINK_NEXT_BOOT':'DISABLE_UPLINK_NEXT_BOOT'},'Startup disimpan. Tidak ada reboot otomatis.',r=>r.enabled===enable);
  };
  globalThis.VeciUplink={reset};
})();
