'use strict';
/* VeCI v2 engineering UI — no credentials persisted and no implicit writes. */
const ROOT_SID = '00000000000000000000000000000000';
let sid = '';
let verifiedPackage = '';
const el = id => document.getElementById(id);

async function rpc(object, method, args = {}, session = sid, durationMs = 8500) {
  const timeout = new AbortController();
  const timer = setTimeout(() => timeout.abort(), durationMs);
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
const firmwareForm = el('firmware-check');
let firmwareCheckGeneration = 0;
function resetFirmwareResult() {
  firmwareCheckGeneration++;
  firmwareForm.querySelector('output').textContent = '';
}
firmwareForm.addEventListener('input', resetFirmwareResult);
firmwareForm.addEventListener('submit', async event => {
  event.preventDefault();
  const generation = ++firmwareCheckGeneration;
  const file = firmwareForm.elements.image.files[0];
  const expected = firmwareForm.elements.digest.value.trim().toLowerCase();
  const output = firmwareForm.querySelector('output');
  try {
    if (!file || !file.size || file.size > 7995392)
      throw Error('Ukuran file harus antara 1 dan 7.995.392 byte.');
    if (!/^[0-9a-f]{64}$/.test(expected)) throw Error('Periksa SHA-256 dari manifest.');
    if (!globalThis.crypto?.subtle) throw Error('Gunakan halaman HTTPS untuk menghitung SHA-256.');
    output.textContent = 'Menghitung SHA-256 pada perangkat ini…';
    const bytes = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
    const actual = Array.from(new Uint8Array(bytes), b => b.toString(16).padStart(2, '0')).join('');
    if (actual !== expected) throw Error('SHA-256 file berbeda dari manifest.');
    if (generation !== firmwareCheckGeneration) return;
    output.textContent = 'Mengunggah file untuk pemeriksaan signature dan kompatibilitas di router…';
    const response = await fetch('/cgi-bin/veci2-verify', {
      method: 'POST', credentials: 'omit', redirect: 'error', cache: 'no-store',
      body: new Blob([sid, expected, file], {type: 'application/octet-stream'})
    });
    if (!response.ok) throw Error('Router menolak pemeriksaan (HTTP ' + response.status + ').');
    const receipt = await response.json();
    if (receipt.verified !== true || receipt.sha256 !== expected)
      throw Error('Hasil pemeriksaan router tidak cocok dengan file.');
    if (generation === firmwareCheckGeneration)
      output.textContent = 'Signature dan kompatibilitas file terverifikasi di router. File sementara telah diproses tanpa instalasi.';
  } catch (error) {
    if (generation === firmwareCheckGeneration) output.textContent = error.message;
  }
});

function describeFirmwareChannel(manifest) {
  if (manifest?.schema !== 1 || manifest.channel !== 'stable' ||
      manifest.target !== 'ramips/mt76x8' || manifest.board !== 'zbtlink,zbt-we5927' ||
      !Array.isArray(manifest.supported_devices) ||
      !manifest.supported_devices.includes(manifest.board))
    throw Error('Manifest tidak cocok dengan profil WE5927.');
  if (manifest.available === false) return 'Belum ada firmware yang diterbitkan di kanal stabil.';
  if (manifest.available !== true || !Number.isInteger(manifest.size) ||
      manifest.size < 1 || manifest.size > 7995392 ||
      typeof manifest.sha256 !== 'string' || !/^[a-fA-F0-9]{64}$/.test(manifest.sha256) ||
      typeof manifest.firmware_url !== 'string' ||
      !manifest.firmware_url.startsWith('https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/download/'))
    throw Error('Metadata rilis tidak lengkap atau tidak valid.');
  return 'Kanal stabil mencantumkan firmware ' + manifest.size + ' byte. SHA-256: ' + manifest.sha256;
}
const channelButton = el('firmware-channel-check');
let channelRequest;
channelButton.addEventListener('click', async () => {
  const output = el('firmware-channel-result');
  const request = new AbortController();
  channelRequest = request;
  const timer = setTimeout(() => request.abort(), 10000);
  channelButton.disabled = true;
  output.textContent = 'Memeriksa kanal stabil…';
  try {
    const response = await fetch('https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/app-feed/channel-stable.json', {
      credentials: 'omit', referrerPolicy: 'no-referrer', cache: 'no-store',
      redirect: 'error', signal: request.signal
    });
    if (!response.ok) throw Error('Kanal GitHub tidak dapat diakses.');
    const message = describeFirmwareChannel(await response.json());
    if (channelRequest === request) output.textContent = message;
  } catch (error) {
    if (channelRequest === request)
      output.textContent = 'Pemeriksaan kanal gagal. ' + error.message;
  } finally {
    clearTimeout(timer);
    if (channelRequest === request) {
      channelRequest = null;
      channelButton.disabled = false;
    }
  }
});

function showWorkspace() {
  globalThis.VeciSmsCenter.activate();
  el('login').hidden = true;
  el('workspace').hidden = false;
  el('logout').hidden = false;
}
function showLogin() {
  channelRequest?.abort();
  channelRequest = null;
  channelButton.disabled = false;
  el('firmware-channel-result').textContent = '';
  resetFirmwareResult();
  firmwareForm.reset();
  globalThis.VeciSmsCenter.logout();
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
  for (const tab of document.querySelectorAll('.tab')) {
    const selected = tab.dataset.page === id || (id === 'apps' && tab.dataset.page === 'settings');
    tab.classList.toggle('active', selected);
    tab.setAttribute('aria-current', selected ? 'page' : 'false');
  }
  if (id === 'network') {
    refreshNetwork();
    refreshEthernet();
  }
  if (id === 'sms') refreshSMS();
  if (id === 'settings') refreshIPv6();
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
async function refreshEthernet() {
  const root = el('ethernet-status');
  try {
    const data = await rpc('veci.v2', 'ethernetPorts');
    if (!data.available || !Array.isArray(data.ports)) throw Error();
    root.replaceChildren(...data.ports.map(({port, link}) => {
      const role = port === 4 ? 'WAN' : 'LAN';
      const label = link === 'up' ? 'Link aktif' : link === 'down' ? 'Tanpa link' : 'Belum terbaca';
      return metric(role + ' · port switch ' + port, label, link === 'up' ? 'good' : '');
    }));
  } catch {
    root.textContent = 'Status switch belum terbaca.';
  }
}
async function refreshNetwork() {
  const root = el('network-status');
  root.replaceChildren(metric('Koneksi', 'Memeriksa...', 'warn'));
  try {
    const data = await rpc('veci.v2', 'status');
    const lte = data.lte_ipv4 === true && data.lte_default_route === true;
    const ap = data.wifi_ap_enabled === true;
    root.replaceChildren(
      metric('LTE / Gateway', lte ? 'Alamat IPv4 dan gateway tersedia' : 'Belum siap', lte ? 'good' : 'warn'),
      metric('Wi-Fi AP', ap ? 'hostapd aktif — beacon belum teruji' : 'AP belum aktif', ap ? 'warn' : 'bad'),
      metric('Netifd', data.netifd_count === 1 ? 'Satu proses normal' : 'Perlu pemeriksaan',
        data.netifd_count === 1 ? 'good' : 'warn')
    );
  } catch (error) {
    root.replaceChildren(metric('Koneksi', 'Status belum tersedia: ' + error.message, 'warn'));
  }
}
let savedIPv6 = null;
async function refreshIPv6() {
  const toggle = el('ipv6-enabled');
  const save = el('ipv6-save');
  toggle.disabled = true;
  save.disabled = true;
  savedIPv6 = null;
  el('ipv6-status').textContent = 'Memeriksa mode IPv6 router...';
  try {
    const data = await rpc('veci.v2.ipv6', 'status');
    if (data.ok !== true || typeof data.enabled !== 'boolean')
      throw Error(String(data.error || 'mode IPv6 tidak dikenal'));
    savedIPv6 = data.enabled;
    toggle.checked = savedIPv6;
    toggle.disabled = false;
    const live = data.runtime_enabled === true ? 'On' :
      data.runtime_enabled === false ? 'Off' : 'Belum terverifikasi';
    el('ipv6-status').textContent = 'Konfigurasi: ' +
      (savedIPv6 ? 'On' : 'Off') + ' · Mode kernel saat ini: ' + live +
      (data.reboot_required === true ? ' · Reboot diperlukan' : '');
  } catch (error) {
    el('ipv6-status').textContent = 'IPv6 tidak dapat diubah: ' + error.message;
  }
}
async function saveIPv6() {
  const toggle = el('ipv6-enabled');
  const button = el('ipv6-save');
  if (savedIPv6 === null || toggle.disabled || toggle.checked === savedIPv6) return;
  const desired = toggle.checked;
  const confirmation = window.confirm(
    (desired ? 'Aktifkan' : 'Nonaktifkan') +
    ' IPv6? Pilihan hanya disimpan. Tidak ada network reload, dan perubahan baru berlaku setelah reboot router manual.'
  );
  if (!confirmation) {
    toggle.checked = savedIPv6;
    button.disabled = true;
    return;
  }
  button.disabled = true;
  toggle.disabled = true;
  try {
    const result = await rpc('veci.v2.ipv6', 'save', {
      enabled: desired,
      confirm: desired ? 'IPV6_ENABLE' : 'IPV6_DISABLE'
    });
    if (result.ok !== true) throw Error(String(result.error || 'Gagal menyimpan IPv6'));
    await refreshIPv6();
  } catch (error) {
    el('ipv6-status').textContent = 'Pilihan belum disimpan: ' + error.message;
    await refreshIPv6();
  }
}
async function refreshSMS() {
  await globalThis.VeciSmsCenter.refresh();
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
  globalThis.VeciSmsCenter.init((object, method, args = {}) => {
    const duration = method === 'sendMessage' ? 46000 :
      method === 'listMessages' ? 13000 : 8500;
    return rpc(object, method, args, sid, duration);
  });
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
    const old = sid;
    globalThis.VeciSmsCenter.logout();
    sid = '';
    showLogin();
    try { await rpc('session', 'destroy', {ubus_rpc_session: old}, old); }
    catch { /* Local logout is already enforced. */ }
  });
  el('refresh').addEventListener('click', async () => {
    notify('');
    try { await refreshOverview(); } catch (error) { notify(error.message); }
  });
  for (const tab of document.querySelectorAll('.tab'))
    tab.addEventListener('click', () => showPage(tab.dataset.page));
  el('ipv6-enabled').addEventListener('change', () => {
    el('ipv6-save').disabled = savedIPv6 === null ||
      el('ipv6-enabled').checked === savedIPv6;
  });
  el('ipv6-save').addEventListener('click', saveIPv6);
  el('open-addons').addEventListener('click', () => showPage('apps'));
  el('back-settings').addEventListener('click', () => showPage('settings'));
  el('package-form').addEventListener('submit', onPackagePreflight);
  el('package-install').addEventListener('click', onPackageInstall);
});
