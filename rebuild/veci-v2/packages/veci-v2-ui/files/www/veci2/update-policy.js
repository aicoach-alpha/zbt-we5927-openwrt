'use strict';
(() => {
  const read = document.getElementById('update-policy-read');
  const mode = document.getElementById('update-policy-mode');
  const save = document.getElementById('update-policy-save');
  const output = document.getElementById('update-policy-status');
  if (!read || !mode || !save || !output) return;
  let busy = false;
  async function work(change = false) {
    if (!sid || busy) return;
    if (change && !window.confirm(mode.value === 'manual'
      ? 'Izinkan instalasi manual yang terverifikasi? Jangan memasang firmware sebelum final siap.'
      : 'Kunci kembali instalasi firmware menjadi verifikasi saja?')) return;
    const session = sid;
    busy = true; read.disabled = save.disabled = true;
    output.textContent = 'Memeriksa kebijakan…';
    try {
      const result = await rpc('veci.v2.updatepolicy',change?'save':'status',
        change?{mode:mode.value}:{},session);
      if (session !== sid) return;
      if (!result.ok) throw Error(result.error || 'Kebijakan tidak tersedia');
      if (!['manual','verify_only'].includes(result.mode)) throw Error('Mode tidak dikenal');
      mode.value = result.mode;
      mode.disabled = false; save.disabled = false;
      output.textContent = result.mode === 'manual' ? 'Instalasi manual diizinkan setelah verifikasi' :
        'Firmware hanya bisa diverifikasi; instalasi dikunci.';
    } catch (err) { if (session === sid) output.textContent = err.message; }
    finally { busy = false; read.disabled = !sid; }
  }
  read.addEventListener('click', () => work(false));
  save.addEventListener('click', () => work(true));
  globalThis.VeciUpdatePolicy = {reset() {
    mode.disabled = save.disabled = true; output.textContent = '';
  }};
})();
