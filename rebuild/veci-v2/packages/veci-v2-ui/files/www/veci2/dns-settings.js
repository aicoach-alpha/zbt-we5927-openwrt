'use strict';
/* Exact-board DNS settings. Write actions only after explicit confirmation. */
(() => {
  const el = id => document.getElementById(id);
  const presets = {
    cloudflare: ['1.1.1.1', '1.0.0.1'],
    google: ['8.8.8.8', '8.8.4.4'],
    quad9: ['9.9.9.9', '149.112.112.112'],
    adguard: ['94.140.14.14', '94.140.15.15']
  };
  let api, loggedIn, saving = false, version = 0;
  function modeUI() {
    const manual = el('dns-mode').value === 'CUSTOM';
    for (const id of ['dns-primary','dns-secondary','dns-preset'])
      el(id).disabled = !manual || saving;
    el('dns-primary').required = manual;
    el('dns-save').disabled = !loggedIn() || saving;
  }
  function parseIPv4(addr) {
    if (!/^(0|[1-9][0-9]{0,2})(\.(0|[1-9][0-9]{0,2})){3}$/.test(addr)) return false;
    const parts = addr.split('.').map(Number);
    return parts.every(x => x >= 0 && x <= 255) &&
      parts[0] !== 0 && parts[0] !== 127 && parts[0] < 224;
  }
  async function refresh() {
    if (!api || !loggedIn() || saving) return;
    const sequence = ++version;
    el('dns-status').textContent = 'Membaca konfigurasi DNS…';
    try {
      const state = await api('veci.v2.dns','status');
      if (!loggedIn() || sequence !== version) return;
      if (state.ok !== true) throw Error(state.error || 'Status DNS tidak tersedia');
      el('dns-mode').value = state.mode;
      el('dns-primary').value = state.primary || '';
      el('dns-secondary').value = state.secondary || '';
      el('dns-preset').value = '';
      el('dns-status').textContent = state.mode === 'AUTO'
        ? 'Aktif: DNS otomatis operator' : 'Aktif: ' + state.primary + (state.secondary ? ' · ' + state.secondary : '');
      modeUI();
    } catch (err) {
      if (loggedIn() && sequence === version) el('dns-status').textContent = 'Gagal membaca DNS: ' + err.message;
      el('dns-save').disabled = true;
    }
  }
  function logout() {
    ++version;
    saving = false;
    for (const id of ['dns-primary','dns-secondary']) el(id).value = '';
    el('dns-save').disabled = true;
    el('dns-status').textContent = 'Login diperlukan.';
  }
  function init(rpc, auth) {
    api = rpc; loggedIn = auth;
    el('dns-mode').addEventListener('change', modeUI);
    el('dns-preset').addEventListener('change', event => {
      const pair = presets[event.target.value];
      if (!pair || saving) return;
      el('dns-mode').value = 'CUSTOM';
      [el('dns-primary').value, el('dns-secondary').value] = pair;
      modeUI();
    });
    el('dns-form').addEventListener('submit', async event => {
      event.preventDefault();
      if (saving || !loggedIn()) return;
      const mode = el('dns-mode').value;
      const primary = el('dns-primary').value.trim();
      const secondary = el('dns-secondary').value.trim();
      if (mode !== 'AUTO' && mode !== 'CUSTOM') return;
      if (mode === 'CUSTOM' && (!parseIPv4(primary) || (secondary && !parseIPv4(secondary)) || primary === secondary)) {
        el('dns-status').textContent = 'Periksa alamat DNS IPv4. Harus valid dan tidak sama.';
        return;
      }
      const msg = mode === 'AUTO' ? 'Kembalikan DNS ke operator?' :
        'Gunakan DNS manual ' + primary + (secondary ? ' dan ' + secondary : '') + '? DNS LAN berhenti sebentar saat diterapkan.';
      if (!window.confirm(msg)) return;
      saving = true; ++version; modeUI();
      el('dns-status').textContent = 'Menyimpan DNS dan memeriksa dnsmasq…';
      try {
        const output = await api('veci.v2.dns', 'set', {mode, primary:mode==='AUTO'?'':primary, secondary:mode==='AUTO'?'':secondary});
        if (!loggedIn()) return;
        if (output.ok !== true) throw Error(output.error || 'Gagal menyimpan DNS');
        el('dns-status').textContent = 'DNS diterapkan. Verifikasi koneksi klien sebelum menganggap DNS sehat.';
      } catch (err) {
        if (loggedIn()) el('dns-status').textContent = 'Gagal menerapkan DNS: ' + err.message;
      } finally {
        saving = false; modeUI();
        if (loggedIn()) refresh();
      }
    });
  }
  globalThis.VeciDnsSettings = {init, refresh, logout};
})();
