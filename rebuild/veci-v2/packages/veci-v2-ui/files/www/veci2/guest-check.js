'use strict';
(() => {
  const button = document.getElementById('guest-status-read');
  const status = document.getElementById('guest-status-result');
  if (!button || !status) return;
  let loading = false;
  button.addEventListener('click', async () => {
    if (!sid || loading) return;
    loading = true; button.disabled = true;
    const session = sid;
    status.textContent = 'Memeriksa konfigurasi guest…';
    try {
      const result = await rpc('veci.v2.guest', 'status', {}, session);
      if (session !== sid) return;
      if (!result.ok) throw Error(result.error || 'Data belum tersedia');
      const labels = {
        not_installed: 'Addon guest belum terpasang',
        not_configured: 'Guest belum dikonfigurasi',
        configuration_needs_audit: 'Konfigurasi guest memerlukan audit',
        configuration_separation_present: 'Pemisahan konfigurasi ada, runtime belum diuji'
      };
      status.textContent = (labels[result.configuration_state] || 'Status tidak diketahui') +
        ' · Guest aktif di konfigurasi: ' + (result.enabled_configured ? 'ya' : 'tidak') +
        ' · Isolasi runtime: belum terverifikasi';
    } catch (error) {
      if (session === sid) status.textContent = error.message;
    } finally { loading = false; button.disabled = !sid; }
  });
  globalThis.VeciGuestCheck = {reset() { status.textContent = ''; button.disabled = false; }};
})();
