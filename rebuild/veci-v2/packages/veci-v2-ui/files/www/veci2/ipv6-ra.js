'use strict';
(() => {
  const select = el('ra-profile'), save = el('ra-save'), status = el('ra-message');
  let revision = '', owner = '', generation = 0;
  async function update(write) {
    const session = sid;
    if (!session || (write && (session !== owner || !revision || !select.value))) return;
    if (write && !confirm('Simpan pengaturan IPv6 LAN untuk aktivasi jaringan berikutnya?')) return;
    const request = ++generation;
    const args = write ? {profile: select.value, revision, confirm: 'SAVE_RA'} : {};
    select.disabled = save.disabled = true;
    try {
      const data = await rpc('veci.v2.ra', write ? 'save' : 'status', args, session);
      if (session !== sid || request !== generation) return;
      if (!data.ok) throw Error(data.error);
      revision = data.revision;
      owner = session;
      select.value = data.profile === 'custom' ? '' : data.profile;
      select.disabled = !data.enabled;
      save.disabled = select.disabled || !select.value;
      status.textContent = !data.enabled ? 'IPv6 utama dinonaktifkan.' : write ?
        'Profil LAN tersimpan untuk aktivasi berikutnya.' : data.profile === 'custom' ?
        'Konfigurasi khusus terdeteksi. Pilih profil untuk menggantinya.' : '';
    } catch (err) {
      if (session === sid && request === generation) status.textContent = err.message;
    }
  }
  select.addEventListener('change', () => { save.disabled = select.disabled || !select.value; });
  el('ra-read').addEventListener('click', () => update(false));
  save.addEventListener('click', () => update(true));
  globalThis.VeciRa = {reset() {
    ++generation;
    revision = owner = status.textContent = select.value = '';
    select.disabled = save.disabled = true;
  }};
})();
