'use strict';
// OEM supplementary controls using the same rpcd services as VeCI.
// Session only in memory; never persist credentials or SMS data.
let sid = '';
const el = id => document.getElementById(id);
const rootSid = '00000000000000000000000000000000';
async function rpc(object, method, args = {}, token = sid) {
  if (!token) throw Error('Login required');
  const abort = new AbortController();
  const timer = setTimeout(() => abort.abort(), method === 'sendMessage' ? 46000 : method === 'listMessages' ? 15000 : 12000);
  try {
    const response = await fetch('/ubus', {method:'POST', credentials:'omit', cache:'no-store',
      headers:{'Content-Type':'application/json'}, signal:abort.signal,
      body:JSON.stringify({jsonrpc:'2.0',id:1,method:'call',params:[token,object,method,args]})});
    const payload = await response.json();
    if (!response.ok || !Array.isArray(payload.result) || payload.result[0] !== 0)
      throw Error('Router rejected the request or service unavailable');
    if (token !== rootSid && token !== sid) throw Error('Session changed');
    return payload.result[1] || {};
  } finally { clearTimeout(timer); }
}
function clearSession() {
  sid = '';
  globalThis.VeciSmsCenter.logout();
  globalThis.VeciDnsSettings.logout();
  el('tools').hidden = true;
  el('login').hidden = false;
  el('login').reset();
  for (const input of el('tools').querySelectorAll('input[type=file]')) input.value = '';
  el('firmware-form').reset();
  el('firmware-result').textContent = '';
  el('backup-restore-file').dispatchEvent(new Event('change'));
  el('backup-message').textContent = '';
  dhcpRevision = ''; el('dhcp-form').reset(); el('dhcp-save').disabled = true;
  el('dhcp-result').textContent = ''; el('traffic-result').textContent = '';
  macRevision=''; el('mac-form').reset(); el('mac-save').disabled=true; el('mac-result').textContent='';
  fwRevision=''; el('fw-save').disabled=true; el('offload-save').disabled=true; el('fw-form').reset(); el('offload-form').reset(); el('fw-result').textContent='';
  guestState=''; el('guest-enable').disabled=true; el('guest-disable').disabled=true; el('guest-result').textContent='';
}
globalThis.VeciSmsCenter.init((object,method,args) => rpc(object,method,args));
globalThis.VeciDnsSettings.init((object,method,args) => rpc(object,method,args), () => Boolean(sid));
el('login').addEventListener('submit', async e => {
  e.preventDefault();
  if (sid || location.protocol !== 'https:') return;
  const button=el('login-button'); if(button.disabled)return;
  button.disabled=true;
  try {
    const answer=await rpc('session','login',{username:el('username').value.trim(),password:el('password').value,timeout:300},rootSid);
    if (!/^[0-9a-f]{32}$/.test(answer.ubus_rpc_session || '') || answer.ubus_rpc_session === rootSid) throw Error('Login denied');
    sid=answer.ubus_rpc_session;
    el('login').reset(); el('login').hidden=true; el('tools').hidden=false;
    el('login-result').textContent='';
    globalThis.VeciSmsCenter.activate();
    await globalThis.VeciSmsCenter.refresh();
    await globalThis.VeciDnsSettings.refresh();
  } catch(err) { el('login-result').textContent=err.message; }
  finally { button.disabled=false; el('password').value=''; }
});
el('logout').onclick=async () => {
  const token=sid; clearSession();
  if(token) await fetch('/ubus',{method:'POST',credentials:'omit',cache:'no-store',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method:'call',params:[token,'session','destroy',{ubus_rpc_session:token}]})}).catch(()=>{});
};
el('sms-refresh').onclick=()=>globalThis.VeciSmsCenter.refresh();
el('dns-refresh').onclick=()=>globalThis.VeciDnsSettings.refresh();
el('firmware-form').onsubmit=async e=>{
  e.preventDefault();
  const token=sid, file=el('firmware-image').files[0], digest=el('firmware-sha').value.trim().toLowerCase(), button=el('firmware-submit');
  if (!token || button.disabled) return;
  button.disabled=true;
  try {
    if (!file || file.size<1 || file.size>7995392 || !/^[0-9a-f]{64}$/.test(digest)) throw Error('Select firmware and expected SHA-256');
    const actual=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await file.arrayBuffer())),v=>v.toString(16).padStart(2,'0')).join('');
    if(actual!==digest || sid!==token)throw Error('Digest or session mismatch');
    el('firmware-result').textContent='Checking signature and board compatibility...';
    const response=await fetch('/cgi-bin/oem-verify',{method:'POST',credentials:'omit',cache:'no-store',redirect:'error',
      body:new Blob([token,digest,file],{type:'application/octet-stream'})});
    const result=await response.json();
    if(sid!==token)return;
    if(!response.ok || result.verified!==true || result.sha256!==digest)throw Error(result.error || 'Firmware not verified');
    el('firmware-result').textContent='Signature and compatibility checks passed. Installation remains disabled on this OEM development interface.';
  } catch(err) { if(sid===token)el('firmware-result').textContent=err.message; }
  finally {button.disabled=false;}
};

// OEM DHCP form reuses the native setPool RPC via the authenticated adapter.
let dhcpRevision = '';
async function oem(op, body, token = sid) {
  if (!token || token !== sid) throw Error('Login required');
  const headers = {'X-OEM-Session':token};
  if(body !== undefined) headers['Content-Type']='application/json';
  const response = await fetch('/cgi-bin/webapi?op='+encodeURIComponent(op),{
    method:body===undefined?'GET':'POST',credentials:'omit',cache:'no-store',
    redirect:'error',headers,body:body===undefined?undefined:JSON.stringify(body)});
  const result=await response.json();
  if(token!==sid)throw Error('Session changed');
  if(!response.ok || result.code!=='1')throw Error(result.reason || 'Router rejected request');
  return result;
}
el('dhcp-refresh').onclick=async ()=>{
  const token=sid, button=el('dhcp-refresh');
  if(!token || button.disabled)return;
  button.disabled=true; dhcpRevision=''; el('dhcp-save').disabled=true;
  try{
    const result=await oem('get_dhcp_config',undefined,token), d=result.data;
    if(!/^[0-9a-f]{64}$/.test(result.revision || '') || !d)throw Error('Revision unavailable');
    if(!['0','1'].includes(d.dhcp_enabled))throw Error('DHCP state invalid');
    el('dhcp-enabled').value=d.dhcp_enabled; el('dhcp-start').value=d.dhcp_start;
    el('dhcp-end').value=d.dhcp_end; el('dhcp-lease').value=d.dhcp_lease;
    dhcpRevision=result.revision; el('dhcp-save').disabled=false;
    el('dhcp-result').textContent='Konfigurasi dibaca dari router.';
  }catch(err){if(sid===token)el('dhcp-result').textContent=err.message;}
  finally{button.disabled=false;}
};
el('dhcp-form').onsubmit=async e=>{
  e.preventDefault();
  const token=sid, revision=dhcpRevision, button=el('dhcp-save');
  if(!token || !revision || button.disabled)return;
  const start=el('dhcp-start').value, end=el('dhcp-end').value, enabled=el('dhcp-enabled').value;
  if(Number(end)<=Number(start)){el('dhcp-result').textContent='Rentang tidak valid.';return;}
  if(!window.confirm('Ubah DHCP LAN? Restart dnsmasq dapat mengganggu klien sementara.'))return;
  button.disabled=true; dhcpRevision='';
  try{
    await oem('set_dhcp_config',{dhcp_start:start,dhcp_end:end,dhcp_enabled:enabled,
      dhcp_lease:el('dhcp-lease').value,revision,confirmation:'SAVE_DHCP_POOL'},token);
    if(sid===token)el('dhcp-result').textContent='Konfigurasi diterima. Baca ulang dan periksa koneksi klien.';
  }catch(err){if(sid===token)el('dhcp-result').textContent=err.message;}
};
el('traffic-refresh').onclick=async ()=>{
  const token=sid, button=el('traffic-refresh');
  if(!token || button.disabled)return;
  button.disabled=true;
  try{
    const result=await rpc('veci.v2.observability','trafficHistory',{},token);
    if(result.ok!==true || result.source!=='kernel_sampled_bytes')throw Error('Traffic history unavailable');
    if(result.state!=='observed_partial'){
      el('traffic-result').textContent='Belum cukup sampel traffic.';
      return;
    }
    const bytes=x=>Number.isSafeInteger(x)&&x>=0?x.toLocaleString('id-ID')+' byte':'Tidak diketahui';
    const line=(name,rx,tx,seconds,gaps)=>name+': RX '+bytes(rx)+' · TX '+bytes(tx)+
      '\nInterval terukur: '+seconds+' detik · gap: '+gaps;
    el('traffic-result').textContent=[
      line('LTE',result.lte_rx_bytes,result.lte_tx_bytes,result.lte_observed_seconds,result.lte_gaps),
      line('LAN',result.lan_rx_bytes,result.lan_tx_bytes,result.lan_observed_seconds,result.lan_gaps)
    ].join('\n\n');
  }catch(err){if(sid===token)el('traffic-result').textContent=err.message;}
  finally{button.disabled=false;}
};

let guestState='';
function guestButtons(){
  el('guest-enable').disabled=!sid||guestState!=='disabled';
  el('guest-disable').disabled=!sid||guestState!=='enabled';
}
el('guest-refresh').onclick=async()=>{
  const token=sid; if(!token)return;
  guestState=''; guestButtons();
  try{
    const result=await rpc('veci.v2.addon','status',{},token);
    if(result.ok!==true || !['absent','unconfigured','enabled','disabled'].includes(result.guest))throw Error('Status guest unavailable');
    guestState=result.guest; guestButtons();
    const labels={absent:'Addon opsional belum terpasang. Guest tidak aktif.',
      unconfigured:'Profil guest belum siap. Provisioning aman diperlukan.',
      enabled:'Dikonfigurasi aktif. Isolasi runtime belum terverifikasi.',
      disabled:'Dikonfigurasi nonaktif.'};
    el('guest-result').textContent=labels[guestState];
  }catch(err){if(sid===token)el('guest-result').textContent=err.message;}
};
async function changeGuest(enable){
  const token=sid, expected=guestState;
  if(!token || expected!==(enable?'disabled':'enabled'))return;
  if(!window.confirm((enable?'Aktifkan':'Nonaktifkan')+' Guest Wi-Fi pada reboot manual berikutnya? Tidak ada reboot otomatis.'))return;
  guestState=''; guestButtons();
  try{
    await oem('set_wifi_guest',{guest_enabled:enable?'1':'0',expected,confirmation:enable?'ENABLE_PORTAL_AP':'DISABLE_PORTAL_AP'},token);
    if(sid===token)el('guest-result').textContent='Konfigurasi disimpan. Reboot manual diperlukan. Status runtime belum terverifikasi.';
  }catch(err){if(sid===token)el('guest-result').textContent=err.message;}
}
el('guest-enable').onclick=()=>changeGuest(true);
el('guest-disable').onclick=()=>changeGuest(false);

let fwRevision='';
function clearFirewall(){fwRevision='';el('fw-save').disabled=true;el('offload-save').disabled=true;}
el('fw-refresh').onclick=async()=>{
  const token=sid,button=el('fw-refresh');if(!token||button.disabled)return;
  button.disabled=true;clearFirewall();
  try{
    const f=await oem('get_fw_setting',undefined,token);
    const n=await oem('get_nat_acceleration',undefined,token);
    if(!/^[0-9a-f]{64}$/.test(f.revision||'')||f.revision!==n.revision||!f.data||!n.data)throw Error('Firewall changed; refresh');
    if(f.data.wan_input!=='REJECT')throw Error('Unexpected WAN policy');
    el('fw-drop').checked=f.data.drop_invalid==='1';
    el('fw-syn').checked=f.data.syn_flood==='1';
    el('fw-offload').checked=n.data.status==='1';
    fwRevision=f.revision;el('fw-save').disabled=false;el('offload-save').disabled=false;
    el('fw-result').textContent='Konfigurasi dibaca. WAN input tetap REJECT.';
  }catch(err){if(sid===token)el('fw-result').textContent=err.message;}
  finally{button.disabled=false;}
};
async function saveFirewall(e,offload){
  e.preventDefault();const token=sid,revision=fwRevision;
  if(!token||!revision)return;
  if(!window.confirm('Terapkan pengaturan firewall? Koneksi aktif dapat terganggu sementara.'))return;
  clearFirewall();
  try{
    const body=offload?{status:el('fw-offload').checked?'1':'0',confirmation:'SAVE_SOFTWARE_OFFLOAD',revision}:
      {drop_invalid:el('fw-drop').checked?'1':'0',syn_flood:el('fw-syn').checked?'1':'0',prohibit_wan_ping:'0',confirmation:'SAVE_FIREWALL_DEFAULTS',revision};
    await oem(offload?'set_nat_acceleration':'set_fw_setting',body,token);
    if(sid===token)el('fw-result').textContent='Disimpan. Baca ulang konfigurasi dan periksa koneksi.';
  }catch(err){if(sid===token)el('fw-result').textContent=err.message;}
}
el('fw-form').onsubmit=e=>saveFirewall(e,false);
el('offload-form').onsubmit=e=>saveFirewall(e,true);

let macRevision='';
el('mac-refresh').onclick=async()=>{
  const token=sid,button=el('mac-refresh');if(!token||button.disabled)return;
  button.disabled=true;macRevision='';el('mac-save').disabled=true;
  try{
    const result=await oem('get_mac_blacklist',undefined,token);
    if(!/^[0-9a-f]{64}$/.test(result.revision||'')||!Array.isArray(result.mac_blacklist))throw Error('MAC rule inventory unavailable');
    el('mac-list').value=result.mac_blacklist.join('\n');
    macRevision=result.revision;el('mac-save').disabled=false;
    el('mac-result').textContent='Daftar dibaca. Cakupan LAN ke WAN.';
  }catch(err){if(sid===token)el('mac-result').textContent=err.message;}
  finally{button.disabled=false;}
};
el('mac-form').onsubmit=async e=>{
  e.preventDefault();const token=sid,revision=macRevision;
  if(!token||!revision)return;
  const list=el('mac-list').value.split(/\s+/).filter(Boolean);
  if(list.length>16||list.some(x=>!/^([0-9a-f]{2}:){5}[0-9a-f]{2}$/i.test(x))){el('mac-result').textContent='Maksimal 16 MAC valid.';return;}
  if(!window.confirm('Terapkan blokir LAN ke WAN? Flow offload dinonaktifkan ketika daftar berisi MAC.'))return;
  macRevision='';el('mac-save').disabled=true;clearFirewall();
  try{
    await oem('set_mac_blacklist',{mac_blacklist:list,revision,confirmation:'SAVE_MAC_BLOCK'},token);
    if(sid===token)el('mac-result').textContent='Konfigurasi diterima. Baca ulang dan uji konektivitas klien.';
  }catch(err){if(sid===token)el('mac-result').textContent=err.message;}
};
