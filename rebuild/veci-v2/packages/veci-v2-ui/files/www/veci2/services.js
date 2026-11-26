'use strict';
// Canonical startup service UI. Optional add-on profiles are owned solely by
// addon-profiles.js and veci.v2.addon; do not bind a nonexistent addon-read.
(() => {
  const read = document.getElementById('startup-read');
  const list = document.getElementById('startup-services');
  const message = document.getElementById('startup-status');
  if (!read || !list || !message)
    throw Error('Required startup service controls are missing from the GUI.');
  let pending = false;
  let generation = 0;

  async function load(change = null) {
    const session = sid;
    if (!session || pending) return;
    pending = true;
    read.disabled = true;
    list.replaceChildren();
    message.textContent = change ? 'Menyimpan pengaturan…' : 'Memeriksa layanan…';
    const current = ++generation;
    try {
      const result = await rpc('veci.v2.services', change ? 'save' : 'status',
        change || {}, session);
      if (sid !== session || current !== generation) return;
      if (result.ok !== true || !Array.isArray(result.services))
        throw Error(String(result.error || 'Status layanan tidak tersedia.'));
      for (const service of result.services) {
        if (typeof service.name !== 'string' ||
            !/^[A-Za-z0-9_.-]{1,64}$/.test(service.name)) continue;
        const row = document.createElement('li');
        row.textContent = service.name +
          (service.enabled === true ? ' · aktif saat boot ' : ' · nonaktif saat boot ');
        if (service.mutable === true) {
          const button = document.createElement('button');
          button.type = 'button';
          button.textContent = service.enabled === true ?
            'Nonaktifkan saat boot' : 'Aktifkan saat boot';
          button.addEventListener('click', () => {
            if (!sid || sid !== session || pending) return;
            if (!window.confirm(button.textContent + ' untuk ' + service.name + '?')) return;
            void load({name:service.name,
              expected:service.enabled === true ? '1' : '0',
              enabled:service.enabled === true ? '0' : '1'});
          });
          row.append(button);
        }
        list.append(row);
      }
      message.textContent = change ? 'Pengaturan startup tersimpan.' :
        'Status startup dibaca dari router. Layanan inti tidak dapat diubah melalui menu ini.';
    } catch (error) {
      if (sid === session && current === generation)
        message.textContent = String(error.message || 'Operasi gagal');
    } finally {
      pending = false;
      read.disabled = false;
    }
  }

  read.addEventListener('click', () => void load());
  window.VeciServices = {
    reset() {
      generation++;
      pending = false;
      read.disabled = true;
      list.replaceChildren();
      message.textContent = '';
      read.disabled = false;
    }
  };
})();
