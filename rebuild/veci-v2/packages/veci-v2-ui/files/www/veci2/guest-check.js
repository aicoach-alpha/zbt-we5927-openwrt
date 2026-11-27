'use strict';
(() => {
  const el = id => document.getElementById(id);
  const button=el('guest-status-read'), status=el('guest-status-result');
  if(!button||!status)return;
  let profile=null,loading=false;
  function reset(){
    profile=null;el('guest-native-form').reset();
    for(const id of ['guest-native-save','guest-native-enable','guest-native-disable'])el(id).disabled=true;
    status.textContent='';
  }
  button.onclick=async()=>{
    if(!sid||loading)return;
    const session=sid;loading=true;button.disabled=true;reset();
    try{
      const x=await rpc('veci.v2.guest','status',{},session,20000);
      if(session!==sid)return;
      if(!x.ok)throw Error(x.error||'Status guest tidak tersedia');
      status.textContent=x.configuration_state+' · Isolasi runtime belum terverifikasi.';
      if(x.mode!=='native'||!/^[0-9a-f]{64}$/.test(x.revision||''))return;
      profile=x;el('guest-native-ssid').value=x.ssid||'';
      el('guest-native-save').disabled=x.configured||!x.native_eligible;
      el('guest-native-enable').disabled=!x.configured||x.enabled_configured||!x.native_eligible;
      el('guest-native-disable').disabled=!x.configured||!x.enabled_configured;
    }catch(e){if(session===sid)status.textContent=e.message;}
    finally{loading=false;button.disabled=false;}
  };
  el('guest-native-form').onsubmit=async e=>{
    e.preventDefault();const token=sid,x=profile;
    if(!token||loading||!x||x.configured||!x.native_eligible)return;
    if(location.protocol!=='https:'||!window.confirm('Siapkan Guest Wi-Fi WPA2 dalam keadaan nonaktif?'))return;
    const args={revision:x.revision,confirmation:'PROVISION_GUEST_DISABLED',ssid:el('guest-native-ssid').value,password:el('guest-native-key').value};
    loading=true;button.disabled=true;reset();
    try{
      const r=await rpc('veci.v2.guest','provisionNative',args,token,25000);
      if(!r.ok||!r.configured||r.enabled_configured!==false)throw Error(r.error||'Provisioning belum terkonfirmasi');
      if(token===sid)status.textContent='Profil disimpan nonaktif. Baca status sebelum mengaktifkan.';
    }catch(e){if(token===sid)status.textContent=e.message;}
    finally{args.password='';loading=false;button.disabled=false;}
  };
  async function toggle(enable){
    const token=sid,x=profile;
    if(!token||loading||!x||!x.configured||x.enabled_configured===enable||(enable&&!x.native_eligible))return;
    if(!window.confirm((enable?'Aktifkan':'Nonaktifkan')+' Guest Wi-Fi pada boot manual berikutnya?'))return;
    loading=true;button.disabled=true;reset();
    try{
      const r=await rpc('veci.v2.guest','setNativeStartup',{revision:x.revision,enabled:enable?'1':'0',confirmation:enable?'ENABLE_NATIVE_GUEST_NEXT_BOOT':'DISABLE_NATIVE_GUEST_NEXT_BOOT'},token,25000);
      if(!r.ok||r.enabled_configured!==enable)throw Error(r.error||'Perubahan belum terkonfirmasi');
      if(token===sid)status.textContent='Konfigurasi startup disimpan. Tidak ada reboot otomatis.';
    }catch(e){if(token===sid)status.textContent=e.message;}
    finally{loading=false;button.disabled=false;}
  }
  el('guest-native-enable').onclick=()=>toggle(true);
  el('guest-native-disable').onclick=()=>toggle(false);
  globalThis.VeciGuestCheck={reset};
})();
