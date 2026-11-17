'use strict';
/* VeCI v2 engineering UI — no credentials persisted and no implicit writes. */
const ROOT_SID = '00000000000000000000000000000000';
let sid = '';
let verifiedPackage = '';
const el = id => document.getElementById(id);

async function rpc(object, method, args = {}, session = sid) {
  const timeout = new AbortController();
  const timer = setTimeout(() => timeout.abort(), 8500);
  try {
    const response = await fetch('/ubus', {
      method: 'POST', cache: 'no-store', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jsonrpc: '2.0', id: 1, method: 'call',
        params: [session, object, method, args]
      }), signal: timeout.signal
    });
    if (!response.ok) throw Error('Router API HTTP ' + response.status);
    const payload = await response.json();
    if (!Array.isArray(payload.result) || payload.result[0] !== 0)
      throw Error('Router API denied or unavailable');
    return payload.result[1] || {};
  } finally {
    clearTimeout(timer);
  }
}
function notify(message) { el('message').textContent = message || ''; }
function metric(name, value, kind = '') {
  const card = document.createElement('article');
  card.className = 'metric';
  const title = document.createElement('h3');
  title.textContent = name;
  const text = document.createElement('strong');
  text.className = kind;
  text.textContent = value;
  card.append(title, text);
  return card;
}
function binaryStatus(value, trueLabel = 'Aktif', falseLabel = 'Tidak aktif') {
  if (value === true) return [trueLabel, 'good'];
  if (value === false) return [falseLabel, 'bad'];
  return ['Belum diverifikasi', 'warn'];
}
function showWorkspace() {
  el('login').hidden = true;
  el('workspace').hidden = false;
  el('logout').hidden = false;
}
function showLogin() {
  sid = '';
  verifiedPackage = '';
  el('logout').hidden = true;
  el('login').hidden = false;
  el('workspace').hidden = true;
  el('password').value = '';
}
function showPage(id) {
  for (const page of document.querySelectorAll('.page'))
    page.hidden = page.id !== id;
  for (const tab of document.querySelectorAll('.tab'))
    tab.classList.toggle('active', tab.dataset.page === id);
  if (id === 'sms') refreshSMS();
  if (id === 'apps') refreshPackages();
}
async function refreshOverview() {
  const data = await rpc('veci.v2', 'status');
  const cards = [];
  let state = binaryStatus(data.board_supported, 'Board sesuai', 'Board tidak sesuai');
  cards.push(metric('Identitas board', state[0], state[1]));
  state = binaryStatus(data.openwrt_supported, 'Versi sesuai', 'Versi tidak sesuai');
  cards.push(metric('OpenWrt 25.12.6', state[0], state[1]));
  const lteLink = data.lte_ipv4 === true && data.lte_default_route === true;
  state = binaryStatus(lteLink, 'IP dan gateway tersedia', 'Belum lengkap');
  cards.push(metric('LTE RNDIS', state[0], state[1]));
  cards.push(metric('Internet end-to-end', 'Belum terverifikasi', 'warn'));
  state = binaryStatus(data.wifi_ap_enabled,
    'Hostapd AP aktif (beacon belum dicek)', 'Access point tidak aktif');
  cards.push(metric('Wi-Fi AP', state[0], state[1]));
  if (data.wifi_ap_missing === true)
    cards.push(metric('Wi-Fi radio/AP mismatch', 'Radio UP, AP hilang', 'bad'));
  cards.push(metric('Proses netifd', String(data.netifd_count || 0) +
    (data.netifd_count === 1 ? ' normal' : ' — perlu audit'),
    data.netifd_count === 1 ? 'good' : 'bad'));
  cards.push(metric('Overlay tersedia',
    Number.isFinite(data.overlay_free_kb) ? data.overlay_free_kb + ' KiB' : 'Unknown'));
  cards.push(metric('RAM tersedia',
    Number.isFinite(data.memory_available_kb) ?
      Math.round(data.memory_available_kb / 1024) + ' MiB' : 'Unknown'));
  el('status-grid').replaceChildren(...cards);
}
async function refreshSMS() {
  const out = el('sms-status');
  out.textContent = 'Memeriksa penyedia SMS...';
  try {
    const provider = await rpc('veci.v2', 'smsProvider');
    if (provider.available !== true) {
      out.textContent = 'Layanan SMS belum terdaftar. Tidak ada perintah AT yang dijalankan.';
      return;
    }
    const sms = await rpc('veci.sms', 'getConfig');
    out.textContent = 'SMS provider: tersedia · ' +
      (sms.enabled === true ? 'Diaktifkan' : 'Nonaktif') +
      ' · Mode: ' + String(sms.mode || 'unknown');
  } catch (error) { out.textContent = 'SMS belum dapat diverifikasi: ' + error.message; }
}
async function refreshPackages() {
  el('package-install').hidden = true;
  verifiedPackage = '';
  const out = el('apk-status');
  out.textContent = 'Memeriksa feed dan penyimpanan...';
  try {
    const status = await rpc('veci.v2.pkg', 'status');
    out.textContent = 'Router: ' + (status.board_ready ? 'sesuai' : 'tidak cocok') +
      ' · Feed: ' + (status.repositories_trusted ? 'terverifikasi' : 'belum terverifikasi') +
      ' · Kapasitas: ' + (status.resources_sufficient ? 'cukup' : 'tidak cukup');
  } catch (error) { out.textContent = 'Package manager belum siap: ' + error.message; }
}
async function onPackagePreflight(event) {
  event.preventDefault();
  verifiedPackage = '';
  el('package-install').hidden = true;
  const name = el('package-name').value.trim();
  const out = el('package-result');
  out.textContent = 'Memvalidasi paket...';
  if (!/^[A-Za-z0-9][A-Za-z0-9+_.-]{0,63}$/.test(name)) {
    out.textContent = 'Format nama paket tidak valid.';
    return;
  }
  try {
    const result = await rpc('veci.v2.pkg', 'preflight', {name});
    if (result.ok !== true) {
      out.textContent = 'Tidak dapat dipasang: ' + String(result.error || 'unknown');
      return;
    }
    verifiedPackage = name;
    out.textContent = 'Prasyarat terpenuhi untuk paket ' + name +
      '. Instalasi dapat memulai ulang layanan; lakukan hanya jika diperlukan.';
    el('package-install').hidden = false;
  } catch (error) { out.textContent = error.message; }
}
async function onPackageInstall() {
  const name = verifiedPackage;
  if (!name) return;
  const accepted = window.confirm('Pasang ' + name +
    '? Instalasi APK dapat mengubah layanan berjalan dan memakai flash. Lanjutkan?');
  if (!accepted) return;
  const button = el('package-install');
  button.disabled = true;
  try {
    const result = await rpc('veci.v2.pkg', 'install',
      {name, confirm: 'INSTALL:' + name});
    if (result.ok !== true) throw Error(String(result.error || 'instalasi gagal'));
    el('package-result').textContent = 'Paket terpasang: ' + name;
    button.hidden = true;
    verifiedPackage = '';
  } catch (error) { el('package-result').textContent = error.message; }
  finally { button.disabled = false; }
}
document.addEventListener('DOMContentLoaded', () => {
  el('login-form').addEventListener('submit', async event => {
    event.preventDefault();
    notify('');
    if (location.protocol !== 'https:' && location.hostname !== 'localhost') {
      notify('Login hanya diizinkan melalui HTTPS. Buka https://alamat-router/veci2/.');
      return;
    }
    const username = el('username').value.trim();
    const password = el('password').value;
    if (!username || !password) return;
    try {
      const answer = await rpc('session', 'login', {username, password}, ROOT_SID);
      const token = answer.ubus_rpc_session;
      if (!/^[0-9a-f]{32}$/.test(token || '')) throw Error('Login ditolak');
      sid = token;
      el('password').value = '';
      showWorkspace();
      await refreshOverview();
    } catch (error) { notify(error.message || 'Login gagal'); }
  });
  el('logout').addEventListener('click', async () => {
    try { await rpc('session', 'destroy', {ubus_rpc_session: sid}); }
    catch { /* Local logout is always enforced. */ }
    showLogin();
  });
  el('refresh').addEventListener('click', async () => {
    notify('');
    try { await refreshOverview(); } catch (error) { notify(error.message); }
  });
  for (const tab of document.querySelectorAll('.tab'))
    tab.addEventListener('click', () => showPage(tab.dataset.page));
  el('package-form').addEventListener('submit', onPackagePreflight);
  el('package-install').addEventListener('click', onPackageInstall);
});
