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
async function firmwareError(response) {
  const fallback = 'Permintaan firmware gagal (HTTP ' + response.status + ').';
  let code;
  try { code = (await response.json()).error; } catch { return fallback; }
  switch (code) {
    case 'installation_locked': return 'Kebijakan router mengunci pemasangan firmware.';
    case 'incompatible_image': return 'Board, target, atau partisi flash tidak cocok dengan image.';
    case 'trust_anchor_failed': return 'Kunci tepercaya router tidak tersedia atau berbeda dari kunci rilis.';
    case 'signature_failed': return 'Signature firmware tidak dapat diverifikasi. Periksa sumber image.';
    case 'digest_failed': return 'Byte image berbeda dari SHA-256 yang dipilih. Periksa file dan manifest.';
    case 'sysupgrade_test_failed': return 'Router menolak image saat uji sysupgrade -T.';
    case 'verification_expired_or_replaced': return 'Tiket sudah kedaluwarsa atau diganti. Verifikasi ulang firmware.';
    case 'verification_busy': return 'Router sedang memproses firmware. Tunggu hingga proses selesai.';
    case 'insufficient_tmp_space': return 'Ruang sementara router tidak cukup untuk memeriksa image.';
    case 'release_download_failed': return 'Router gagal mengunduh aset rilis GitHub. Periksa koneksi router.';
    default: return fallback;
  }
}
const firmwareForm = el('firmware-check');
let installCandidate = null;
const installButton = el('firmware-install');
function clearInstallCandidate() {
  installCandidate = null;
  installButton.hidden = true;
}
function offerInstall(receipt, payload, ota) {
  clearInstallCandidate();
  if (!/^[0-9a-f]{64}$/.test(receipt.ticket || ''))
    throw Error('Router tidak memberikan tiket instalasi yang valid.');
  if (receipt.install_allowed === false) return;
  installCandidate = {digest: receipt.sha256, ticket: receipt.ticket, payload, ota};
  installButton.hidden = false;
}
installButton.addEventListener('click', async () => {
  const candidate = installCandidate;
  if (!candidate || !window.confirm('Pasang firmware SHA-256 ' + candidate.digest +
      ' dengan mempertahankan konfigurasi? Router akan reboot dan koneksi terputus.')) return;
  const session = sid;
  clearInstallCandidate();
  const status = el('firmware-install-result');
  status.textContent = 'Memeriksa ulang file dan mengirim permintaan instalasi…';
  try {
    const response = await fetch('/cgi-bin/veci2-verify?' + (candidate.ota ? 'stable-apply' : 'apply'), {
      method: 'POST', credentials: 'omit', redirect: 'error', cache: 'no-store',
      body: new Blob([session, candidate.digest, candidate.ticket, candidate.payload], {type:'application/octet-stream'})
    });
    if (sid !== session) return;
    if (response.status !== 202) throw Error(await firmwareError(response));
    const result = await response.json();
    if (result.accepted !== true || result.sha256 !== candidate.digest) throw Error('Respons instalasi tidak cocok.');
    if (sid === session) status.textContent = 'Permintaan diterima. Periksa versi firmware setelah router kembali online.';
  } catch (error) {
    if (sid === session) status.textContent = 'Status instalasi belum terkonfirmasi. Periksa router sebelum mencoba lagi. ' + error.message;
  }
});

let firmwareCheckGeneration = 0;
function resetFirmwareResult() {
  clearInstallCandidate();
  const generation = ++firmwareCheckGeneration;
  verifyRelease.disabled = false;
  firmwareForm.querySelector('output').textContent = '';
  if (stableRelease)
    el('firmware-channel-result').textContent = describeFirmwareChannel(stableRelease);
  return generation;
}
firmwareForm.addEventListener('input', resetFirmwareResult);
firmwareForm.addEventListener('submit', async event => {
  event.preventDefault();
  const generation = resetFirmwareResult();
  const session = sid;
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
    if (generation !== firmwareCheckGeneration || sid !== session) return;
    output.textContent = 'Mengunggah file untuk pemeriksaan signature dan kompatibilitas di router…';
    const response = await fetch('/cgi-bin/veci2-verify', {
      method: 'POST', credentials: 'omit', redirect: 'error', cache: 'no-store',
      body: new Blob([session, expected, file], {type: 'application/octet-stream'})
    });
    if (!response.ok) throw Error(await firmwareError(response));
    const receipt = await response.json();
    if (receipt.verified !== true || receipt.sha256 !== expected)
      throw Error('Hasil pemeriksaan router tidak cocok dengan file.');
    if (generation !== firmwareCheckGeneration || sid !== session) return;
    offerInstall(receipt, file, false);
    output.textContent = 'Signature dan kompatibilitas file terverifikasi di router. File sementara telah diproses tanpa instalasi.';
  } catch (error) {
    if (generation === firmwareCheckGeneration && sid === session) output.textContent = error.message;
  }
});

const releaseAsset = /^https:\/\/github\.com\/aicoach-alpha\/zbt-we5927-openwrt\/releases\/download\/([A-Za-z0-9_-][A-Za-z0-9._-]{0,127})\/([A-Za-z0-9_-][A-Za-z0-9._-]{0,127})$/;
let stableRelease = null;
const verifyRelease = el('firmware-channel-verify');
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
      !releaseAsset.exec(manifest.firmware_url))
    throw Error('Metadata rilis tidak lengkap atau tidak valid.');
  return 'Kanal stabil mencantumkan firmware ' + manifest.size + ' byte. SHA-256: ' + manifest.sha256;
}
const channelButton = el('firmware-channel-check');
let channelRequest;
channelButton.addEventListener('click', async () => {
  const output = el('firmware-channel-result');
  const request = new AbortController();
  resetFirmwareResult();
  channelRequest = request;
  stableRelease = null;
  verifyRelease.hidden = true;
  const timer = setTimeout(() => request.abort(), 10000);
  channelButton.disabled = true;
  output.textContent = 'Memeriksa kanal stabil…';
  try {
    const response = await fetch('https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/app-feed/channel-stable.json', {
      credentials: 'omit', referrerPolicy: 'no-referrer', cache: 'no-store',
      redirect: 'error', signal: request.signal
    });
    if (!response.ok) throw Error('Kanal GitHub tidak dapat diakses.');
    const manifest = await response.json();
    const message = describeFirmwareChannel(manifest);
    if (channelRequest === request) {
      output.textContent = message;
      stableRelease = manifest.available ? manifest : null;
      verifyRelease.hidden = !stableRelease;
    }
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

verifyRelease.addEventListener('click', async () => {
  const manifest = stableRelease;
  if (!manifest || verifyRelease.disabled) return;
  const [, tag, asset] = releaseAsset.exec(manifest.firmware_url);
  const digest = manifest.sha256.toLowerCase();
  const output = el('firmware-channel-result');
  const generation = resetFirmwareResult();
  const session = sid;
  verifyRelease.disabled = true;
  output.textContent = 'Router sedang mengunduh dan memeriksa firmware…';
  try {
    const response = await fetch('/cgi-bin/veci2-verify?stable', {
      method: 'POST', credentials: 'omit', redirect: 'error', cache: 'no-store',
      body: new Blob([session, digest, manifest.size + '\n' + tag + '\n' + asset + '\n'], {type: 'application/octet-stream'})
    });
    if (!response.ok) throw Error(await firmwareError(response));
    const receipt = await response.json();
    if (receipt.verified !== true || receipt.sha256 !== digest) throw Error('SHA-256 hasil verifikasi berbeda.');
    if (generation !== firmwareCheckGeneration || sid !== session) return;
    offerInstall(receipt, [manifest.size, tag, asset, ''].join('\n'), true);
    output.textContent = 'Firmware kanal stabil terverifikasi di router. Instalasi belum dimulai.';
  } catch (error) {
    if (generation === firmwareCheckGeneration && sid === session) output.textContent = error.message;
  } finally {
    if (generation === firmwareCheckGeneration) verifyRelease.disabled = false;
  }
});

function showWorkspace() {
  showPage("overview");
  globalThis.VeciSmsCenter.activate();
  el('login').hidden = true;
  el('workspace').hidden = false;
  el('logout').hidden = false;
}
function showLogin() {
  el("backup-message").textContent = "";
  globalThis.VeciAccess?.reset();
  globalThis.VeciSimLock?.reset();
  globalThis.VeciFirewall?.reset();
  globalThis.VeciTime?.reset();
  el('diag-result').textContent = '';
  el('diag-target').value = '';
  el('diag-run').disabled = false;
  el('lte-apn').value = '';
  el('lte-apn').disabled = true;
  el('lte-apn-save').disabled = true;
  el('lte-sim-switch').disabled = true;
  el('firmware-install-result').textContent = '';
  stableRelease = null;
  verifyRelease.hidden = true;
  ltePolicyRequest++;
  lteSaving = false;
  el('lte-policy-change').disabled = true;
  el('lte-policy-status').textContent = '';
  globalThis.VeciWifiControls?.reset();
  globalThis.VeciRa?.reset();
  globalThis.VeciServices?.reset();
  globalThis.VeciLeds?.reset();
  globalThis.VeciInterfaces?.reset();
  el('wifi-channel-auto').disabled = true;
  el('wifi-name').value = '';
  el('wifi-name').disabled = true;
  el('wifi-name-save').disabled = true;
  visibilityRequest++;
  configuredVisible = null;
  savingVisibility = false;
  el('wifi-visibility-change').disabled = true;
  el('wifi-visibility-status').textContent = '';
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
    refreshVisibility();
    refreshLtePolicy();
  }
  if (id === 'sms') refreshSMS();
  if (id === 'settings') { refreshIPv6(); refreshUpdatePolicy(); }
  if (id === 'apps') refreshPackages();
}
function primaryApStatus(data) {
  if (data.wifi_ap_enabled === true) return ['Hostapd aktif, beacon belum diuji', 'warn'];
  if (data.wifi_ap_configured === false) return ['Dinonaktifkan di konfigurasi', ''];
  if (data.wifi_ap_configured !== true || data.wifi_radio_config_up == null)
    return ['Status AP belum terverifikasi', 'warn'];
  return ['AP utama belum aktif', 'bad'];
}
async function refreshOverview() {
  const data = await rpc('veci.v2', 'status');
  const cards = [];
  let state = binaryStatus(data.board_supported, 'Board sesuai', 'Board tidak sesuai');
  cards.push(metric('Identitas board', state[0], state[1]));
  state = binaryStatus(data.openwrt_supported, 'Versi sesuai', 'Versi tidak sesuai');
  cards.push(metric('OpenWrt 25.12.6', state[0], state[1]));
  const lteLink = typeof data.lte_ipv4 === 'boolean' && typeof data.lte_default_route === 'boolean'
    ? data.lte_ipv4 && data.lte_default_route : null;
  state = binaryStatus(lteLink, 'IP dan gateway tersedia', 'Belum lengkap');
  cards.push(metric('LTE RNDIS', state[0], state[1]));
  cards.push(metric('Internet end-to-end', 'Belum terverifikasi', 'warn'));
  cards.push(metric('Wi-Fi AP', ...primaryApStatus(data)));
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
let visibilityRequest = 0;
let configuredVisible = null;
let savingVisibility = false;
async function refreshVisibility(method = 'status', params = {}) {
  if (savingVisibility) return;
  const sequence = ++visibilityRequest;
  const session = sid;
  const button = el('wifi-visibility-change');
  const status = el('wifi-visibility-status');
  const name = el('wifi-name');
  const saveName = el('wifi-name-save');
  const autoChannel = el('wifi-channel-auto');
  autoChannel.disabled = true;
  name.disabled = true;
  saveName.disabled = true;
  button.disabled = true;
  configuredVisible = null;
  savingVisibility = method !== 'status';
  status.textContent = savingVisibility ? 'Menyimpan konfigurasi…' : 'Membaca konfigurasi…';
  try {
    const data = await rpc('veci.v2.wifi', method, params, session);
    if (sequence !== visibilityRequest || sid !== session) return;
    if (!data.ok || typeof data.configured_visible !== 'boolean')
      throw Error(data.error || 'Status tidak tersedia');
    configuredVisible = data.configured_visible;
    status.textContent = (configuredVisible ? 'Konfigurasi: SSID ditampilkan.' : 'Konfigurasi: SSID disembunyikan.') +
      ' Perubahan berlaku saat Wi-Fi berikutnya dimulai. Beacon perlu diperiksa dari perangkat klien.';
    if (/^(?:auto|[1-9]|1[0-4])$/.test(data.configured_channel)) {
      status.textContent += ' Kanal tersimpan: ' + (data.configured_channel === 'auto' ? 'otomatis' : data.configured_channel) + '.';
      autoChannel.disabled = data.configured_channel === 'auto';
    }
    button.textContent = configuredVisible ? 'Sembunyikan SSID' : 'Tampilkan SSID';
    if (typeof data.ssid_hex === 'string' && /^(?:[0-9a-f]{2}){0,32}$/.test(data.ssid_hex)) {
      const bytes = Uint8Array.from(data.ssid_hex.match(/../g) || [], byte => parseInt(byte, 16));
      try {
        const stored = new TextDecoder('utf-8', {fatal: true, ignoreBOM: true}).decode(bytes);
        if (/[\x00-\x1f\x7f]/.test(stored)) throw Error();
        name.value = stored;
      } catch {
        name.value = '';
        status.textContent += ' Nama saat ini tidak dapat ditampilkan sebagai teks.';
      }
      name.disabled = false;
      saveName.disabled = false;
    }
    button.disabled = false;
  } catch (error) {
    if (sequence === visibilityRequest && sid === session) status.textContent = error.message;
  } finally {
    if (sequence === visibilityRequest) savingVisibility = false;
  }
}
let ltePolicyRequest = 0;
let lteSaving = false;
async function refreshLtePolicy(action, apn) {
  if (lteSaving) return;
  const sequence = ++ltePolicyRequest;
  const session = sid;
  const status = el('lte-policy-status');
  const button = el('lte-policy-change');
  button.disabled = true;
  el('lte-apn').disabled = true;
  el('lte-apn-save').disabled = true;
  el('lte-sim-switch').disabled = true;
  lteSaving = Boolean(action);
  status.textContent = action ? 'Menyimpan pilihan…' : 'Membaca pilihan…';
  try {
    const method = action === 'queueSim' ? 'queueSim' : action === 'setApn' ? 'setApn' : action ? 'setFailover' : 'status';
    const args = method === 'queueSim' ? {slot: apn} : method === 'setApn' ? {apn} : action ? {action} : {};
    const data = await rpc('veci.v2.lte', method, args, session);
    if (sequence !== ltePolicyRequest || sid !== session) return;
    if (data.ok !== true || typeof data.auto_failover !== 'boolean')
      throw Error(data.error || 'Pilihan failover tidak tersedia.');
    const slot = [1, 2].includes(data.configured_slot) ? 'SIM ' + data.configured_slot : 'belum diketahui';
    status.textContent = 'Slot tersimpan: ' + slot + '. Failover otomatis ' + (data.auto_failover ? 'aktif.' : 'nonaktif.');
    const selector = [1, 2].includes(data.selector_slot) ? 'SIM ' + data.selector_slot : 'belum terbaca';
    status.textContent += ' Posisi selektor: ' + selector + '.';
    const switchMessages = {
      queued: 'Perpindahan menunggu siklus manajer LTE.', switching: 'Sedang memindahkan SIM.',
      interrupted: 'Perpindahan terhenti. Periksa posisi selektor sebelum mencoba kembali.', expired: 'Permintaan kedaluwarsa.', selector_changed: 'Posisi selektor berubah sebelum permintaan diproses.',
      selection_failed: 'Pemilihan SIM gagal. Periksa log LTE.', interface_started: 'Antarmuka LTE telah dimulai pada SIM tujuan.',
      restored: 'Inisialisasi gagal. SIM sebelumnya telah dipulihkan.', recovery_failed: 'Pemulihan koneksi gagal. Periksa log LTE.'
    };
    if (switchMessages[data.switch_state]) status.textContent += ' ' + switchMessages[data.switch_state];
    const switchButton = el('lte-sim-switch');
    if ([1, 2].includes(data.selector_slot) && !['queued', 'switching'].includes(data.switch_state)) {
      switchButton.dataset.slot = String(3 - data.selector_slot);
      switchButton.textContent = 'Pindah ke SIM ' + switchButton.dataset.slot;
      switchButton.disabled = false;
    }
    button.textContent = data.auto_failover ? 'Nonaktifkan failover' : 'Aktifkan failover';
    button.dataset.action = data.auto_failover ? 'DISABLE_FAILOVER' : 'ENABLE_FAILOVER';
    el('lte-apn').value = data.configured_apn || '';
    el('lte-apn').disabled = false;
    el('lte-apn-save').disabled = false;
    if (method === 'setApn') status.textContent += ' APN tersimpan untuk konfigurasi modem berikutnya.';
    button.disabled = false;
  } catch (error) {
    if (sequence === ltePolicyRequest && sid === session) status.textContent = error.message;
  } finally {
    if (sequence === ltePolicyRequest) lteSaving = false;
  }
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
const lteMonitorLabels = new Map([
  ['healthy', 'Koneksi terdeteksi'], ['checking', 'Memeriksa koneksi'],
  ['upstream_degraded', 'Gateway merespons, akses luar terganggu'],
  ['icmp_degraded_https_ok', 'HTTPS berhasil, ping gagal'],
  ['dhcp_renew', 'Memperbarui DHCP'], ['recovered_dhcp', 'Pulih setelah pembaruan DHCP'],
  ['dhcp_cooldown', 'Menunggu percobaan DHCP berikutnya'],
  ['interface_recovery', 'Memulihkan interface'], ['recovered_interface', 'Interface pulih'],
  ['interface_cooldown', 'Menunggu percobaan pemulihan interface'],
  ['modem_soft_reconnect', 'Menyambungkan ulang modem'], ['recovered_soft', 'Modem tersambung kembali'],
  ['last_resort_power_cycle', 'Mengulang daya modem'], ['power_cycle_failed', 'Pengulangan daya modem gagal'],
  ['power_cycle_cooldown', 'Menunggu percobaan pemulihan modem'],
  ['opt_in_sim_failover', 'Mencoba SIM cadangan'], ['sim_failover_failed', 'Percobaan SIM cadangan gagal']
]);
const lteUsbLabels = new Map([
  ['invalid_configuration', 'Nama interface LTE tidak valid'],
  ['modem_missing', 'Modem USB yang dikonfigurasi belum terdeteksi'],
  ['interface_missing', 'Interface data USB belum tersedia'],
  ['other_device', 'Interface data berasal dari perangkat USB lain'],
  ['driver_mismatch', 'Interface modem belum memakai driver RNDIS'],
  ['carrier_down', 'Driver RNDIS terpasang, link data turun'],
  ['carrier_up', 'Driver RNDIS terpasang, link data aktif'],
  ['carrier_unknown', 'Driver RNDIS terpasang, status link belum terbaca']
]);
async function refreshNetwork() {
  const root = el('network-status');
  root.replaceChildren(metric('Koneksi', 'Memeriksa...', 'warn'));
  try {
    const data = await rpc('veci.v2', 'status');
    const ipv4 = binaryStatus(data.lte_ipv4, 'Alamat tersedia', 'Belum mendapat alamat');
    const gateway = binaryStatus(data.lte_default_route, 'Rute tersedia', 'Belum ada rute default');
    root.replaceChildren(
      metric('Modem USB / RNDIS', lteUsbLabels.get(data.lte_usb_state) || 'Belum terbaca'),
      metric('LTE / IPv4', ...ipv4),
      metric('LTE / Gateway', ...gateway),
      metric('Observasi terakhir monitor LTE', lteMonitorLabels.get(data.lte_monitor_stage) || 'Belum tersedia'),
      metric('Wi-Fi AP', ...primaryApStatus(data)),
      metric('Kanal AP utama', Number.isInteger(data.wifi_ap_channel)
        ? String(data.wifi_ap_channel) : 'Belum terbaca'),
      metric('Netifd', data.netifd_count === 1 ? 'Satu proses normal' : 'Perlu pemeriksaan',
        data.netifd_count === 1 ? 'good' : 'warn')
    );
  } catch (error) {
    root.replaceChildren(metric('Koneksi', 'Status belum tersedia: ' + error.message, 'warn'));
  }
}
let savedIPv6 = null;
let policySaving = false;
let policyRequest = 0;
async function refreshUpdatePolicy(save = false) {
  if (policySaving) return;
  const request = ++policyRequest;
  const session = sid;
  const select = el('update-policy');
  const button = el('update-policy-save');
  const status = el('update-policy-status');
  const mode = select.value;
  if (save && !window.confirm('Simpan kebijakan untuk upgrade manual dan OTA?')) return;
  select.disabled = button.disabled = true;
  policySaving = save;
  try {
    const data = await rpc('veci.v2.updatepolicy', save ? 'save' : 'status', save ? {mode} : {}, session);
    if (sid !== session || request !== policyRequest) return;
    if (!data.ok || !['manual', 'verify_only'].includes(data.mode)) throw Error(data.error || 'Kebijakan belum terbaca');
    select.value = data.mode;
    if (save || data.mode === 'verify_only') clearInstallCandidate();
    status.textContent = data.mode === 'verify_only' ? 'Pemasangan terkunci. Verifikasi tersedia.' : 'Pemasangan membutuhkan konfirmasi.';
    select.disabled = button.disabled = false;
  } catch (error) {
    if (sid === session && request === policyRequest) status.textContent = error.message;
  } finally {
    if (request === policyRequest) policySaving = false;
  }
}
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
  let authenticating = false;
  let signingOut = false;
  el('login-form').addEventListener('submit', async event => {
    event.preventDefault();
    notify('');
    if (location.protocol !== 'https:' && location.hostname !== 'localhost') {
      notify('Login hanya diizinkan melalui HTTPS. Buka https://alamat-router/veci2/.');
      return;
    }
    const username = el('username').value.trim();
    const password = el('password').value;
    if (!username || !password || authenticating || signingOut || sid) return;
    authenticating = true;
    try {
      const answer = await rpc('session', 'login', {username, password}, ROOT_SID);
      const token = answer.ubus_rpc_session;
      if (typeof token !== 'string' || token === ROOT_SID || !/^[0-9a-f]{32}$/.test(token)) throw Error('Login ditolak');
      sid = token;
      const scopes = answer.acls && answer.acls['access-group'];
      const groups = scopes && typeof scopes === 'object' ? Object.entries(scopes) : [];
      const rights = groups.filter(([group, modes]) => group.startsWith('veci-v2-') &&
        Array.isArray(modes)).map(([group, modes]) => {
          const labels = [];
          if (modes.includes('read')) labels.push('baca');
          if (modes.includes('write')) labels.push('tulis');
          return labels.length ? group + ' (' + labels.join(', ') + ')' : '';
        }).filter(Boolean).sort();
      el('session-permissions').textContent = rights.length ? rights.join(' · ') :
        'Rincian grup VeCI tidak tersedia.';
      el('session-account').textContent = username;
      showPage('overview');
      showWorkspace();
      await refreshOverview();
    } catch (error) { notify(error.message || 'Login gagal'); }
    finally {
      authenticating = false;
      el('password').value = '';
    }
  });
  el('logout').addEventListener('click', async () => {
    if (!sid || signingOut) return;
    signingOut = true;
    const old = sid;
    showLogin();
    el('session-permissions').textContent = '';
    el('session-account').textContent = '';
    try { await rpc('session', 'destroy', {}, old); }
    catch {
      window.alert('Anda sudah keluar di browser. Router belum mengonfirmasi penutupan sesi.');
    } finally { location.reload(); }
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
  el('lte-apn-form').addEventListener('submit', event => {
    event.preventDefault();
    const input = el('lte-apn');
    if (input.disabled || lteSaving) return;
    if (!/^[A-Za-z0-9._-]{1,100}$/.test(input.value)) {
      el('lte-policy-status').textContent = 'APN hanya boleh berisi huruf, angka, titik, garis bawah, atau tanda hubung.';
      return;
    }
    if (window.confirm('Simpan APN ' + input.value + ' untuk konfigurasi modem berikutnya?'))
      refreshLtePolicy('setApn', input.value);
  });
  el('lte-sim-refresh').addEventListener('click', () => refreshLtePolicy());
  el('lte-sim-switch').addEventListener('click', event => {
    const button = event.currentTarget;
    const slot = button.dataset.slot;
    if (!button.disabled && !lteSaving && ['1', '2'].includes(slot) &&
        window.confirm('Pindah ke SIM ' + slot + '? Modem akan dimulai ulang dan koneksi LTE akan terputus sementara.'))
      refreshLtePolicy('queueSim', slot);
  });
  el('lte-policy-change').addEventListener('click', event => {
    const button = event.currentTarget;
    if (button.disabled) return;
    const message = button.dataset.action === 'ENABLE_FAILOVER' ?
      'Izinkan modem mencoba SIM lain saat koneksi gagal? Perpindahan dapat memutus LTE sementara.' :
      'Nonaktifkan perpindahan SIM otomatis berikutnya?';
    if (window.confirm(message)) refreshLtePolicy(button.dataset.action);
  });
  el('wifi-channel-auto').addEventListener('click', () => {
    if (!savingVisibility && window.confirm('Simpan pemilihan kanal otomatis untuk Wi-Fi 2,4 GHz saat radio berikutnya dimulai?'))
      refreshVisibility('setAutoChannel', {action: 'AUTO_CHANNEL_2G'});
  });
  el('wifi-name-form').addEventListener('submit', event => {
    event.preventDefault();
    const input = el('wifi-name');
    if (savingVisibility || input.disabled) return;
    const bytes = new TextEncoder().encode(input.value);
    if (!bytes.length || bytes.length > 32 || bytes.some(byte => byte < 32 || byte === 127)) {
      el('wifi-visibility-status').textContent = 'Gunakan 1–32 byte tanpa karakter kontrol.';
      return;
    }
    if (window.confirm('Simpan nama Wi-Fi utama? Nama baru berlaku saat Wi-Fi berikutnya dimulai.')) {
      const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
      refreshVisibility('setSsid', {ssid_hex: hex});
    }
  });
  el('wifi-visibility-change').addEventListener('click', () => {
    if (configuredVisible === null || savingVisibility) return;
    const label = configuredVisible ? 'Sembunyikan' : 'Tampilkan';
    if (window.confirm(label + ' SSID utama pada konfigurasi tersimpan? Radio tetap berjalan.'))
      refreshVisibility('setVisibility', {action: configuredVisible ? 'HIDE_SSID' : 'SHOW_SSID'});
  });
  el('update-policy-save').addEventListener('click', () => refreshUpdatePolicy(true));
  el('ipv6-save').addEventListener('click', saveIPv6);
  const diagnostic = el('diag-method');
  const needsHost = () => ['lookup', 'ping', 'trace'].includes(diagnostic.value);
  diagnostic.addEventListener('change', () => {
    el('diag-target-label').hidden = !needsHost();
    el('diag-target').required = needsHost();
  });
  el('diag-form').addEventListener('submit', async event => {
    event.preventDefault();
    const button = el('diag-run');
    if (button.disabled || !sid) return;
    const session = sid;
    const output = el('diag-result');
    button.disabled = true;
    output.textContent = 'Mengambil hasil…';
    try {
      const params = needsHost() ? {target: el('diag-target').value.trim()} : {};
      const reply = await rpc('veci.v2.diag', diagnostic.value, params, session, 14000);
      if (sid !== session) return;
      if (!reply.ok || !Array.isArray(reply.lines)) throw Error(reply.error || 'Hasil tidak tersedia');
      const lines = reply.lines.join('\n');
      output.textContent = reply.exit_code === 0 ? lines || 'Tidak ada entri.' :
        'Pemeriksaan gagal (kode ' + reply.exit_code + ').\n' + lines;
    } catch (error) {
      if (sid === session) output.textContent = error.message;
    } finally {
      if (sid === session) button.disabled = false;
    }
  });
  el('open-addons').addEventListener('click', () => showPage('apps'));
  el('back-settings').addEventListener('click', () => showPage('settings'));
  el('package-form').addEventListener('submit', onPackagePreflight);
  el('package-install').addEventListener('click', onPackageInstall);
});
