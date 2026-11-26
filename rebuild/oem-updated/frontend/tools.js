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
