'use strict';
(() => {
  const panel = el('wifi-extra'), controls = el('wifi-controls'), status = el('wifi-extra-status');
  const access = el('station-acl').elements, security = el('wifi-auth').elements, fixed = el('wifi-fixed').elements;
  let generation = 0;
  function render(data) {
    access.mode.value = data.access || '';
    access.addresses.value = (data.addresses || []).join('\n');
    security.mode.value = data.encryption || '';
    fixed.channel.replaceChildren();
    for (const channel of data.channels || []) fixed.channel.add(new Option(String(channel), String(channel)));
    fixed.channel.selectedIndex = -1;
    el('station-list').textContent = Array.isArray(data.clients) ?
      (data.clients.join(', ') || 'Belum ada klien terhubung.') : 'Status klien belum tersedia.';
  }
  async function run(method = 'info', args = {}) {
    const session = sid;
    if (!session) return;
    const gen = ++generation;
    controls.disabled = true;
    status.textContent = 'Memproses…';
    try {
      async function call(name, params) {
        const data = await rpc('veci.v2.wifi', name, params, session, name === 'survey' ? 16000 : 8500);
        if (!data.ok) throw Error(data.error || 'Permintaan gagal');
        return data;
      }
      const data = await call(method, args);
      if (gen !== generation || sid !== session) return;
      if (method === 'survey') {
        el('scan-results').textContent = data.networks.map(n => (n.ssid || '(tersembunyi)') + ' · ' +
          n.bssid + ' · ' + n.frequency_mhz + ' MHz · ' + (n.signal_dbm ?? '?') + ' dBm').join('\n') || 'Tidak ada jaringan terdeteksi.';
      } else {
        const info = method === 'info' ? data : await call('info', {});
        if (gen !== generation || sid !== session) return;
        render(info);
      }
      status.textContent = method.startsWith('set') ? 'Tersimpan untuk Wi-Fi berikutnya dimulai.' : '';
    } catch (error) {
      if (gen === generation && sid === session) status.textContent = error.message;
    } finally {
      if (gen === generation && sid === session) controls.disabled = false;
    }
  }
  panel.addEventListener('toggle', () => { if (panel.open) run(); });
  el('stations-refresh').addEventListener('click', () => run());
  el('station-acl').addEventListener('submit', event => {
    event.preventDefault();
    if (window.confirm('Simpan filter klien? Perangkat di luar daftar izin bisa kehilangan akses saat radio dimulai kembali.'))
      run('setAccess', {mode: access.mode.value, addresses: access.addresses.value.trim().replace(/\s+/g, ' ')});
  });
  el('wifi-auth').addEventListener('submit', event => {
    event.preventDefault();
    if (!/^[ -~]{8,63}$/.test(security.key.value)) { status.textContent = 'Gunakan 8–63 karakter ASCII cetak.'; return; }
    if (!window.confirm('Simpan pengamanan baru untuk Wi-Fi utama?')) return;
    const hex = Array.from(new TextEncoder().encode(security.key.value), b => b.toString(16).padStart(2, '0')).join('');
    security.key.value = '';
    run('setAuth', {mode: security.mode.value, key_hex: hex});
  });
  el('wifi-fixed').addEventListener('submit', event => {
    event.preventDefault();
    if (window.confirm('Simpan kanal tetap?')) run('setChannel', {channel: fixed.channel.value});
  });
  el('wifi-scan').addEventListener('click', () => {
    if (window.confirm('Mulai survei pasif? Radio dapat meninggalkan kanal sebentar.')) run('survey');
  });
  globalThis.VeciWifiControls = {reset() {
    ++generation;
    panel.open = false;
    controls.disabled = true;
    access.addresses.value = security.key.value = '';
    for (const id of ['station-list', 'scan-results', 'wifi-extra-status']) el(id).textContent = '';
  }};
})();
