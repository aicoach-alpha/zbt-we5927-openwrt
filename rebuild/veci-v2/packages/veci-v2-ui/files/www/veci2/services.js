'use strict';
(() => {
  const read = el('startup-read'), list = el('startup-services'), message = el('startup-status');
  let pending = false;
  async function load(args) {
    const session = sid;
    if (!session || pending) return;
    pending = true;
    read.disabled = true;
    list.replaceChildren();
    message.textContent = 'Memproses…';
    try {
      const data = await rpc('veci.v2.services', args ? 'save' : 'status', args || {}, session);
      if (session !== sid) return;
      if (!data.ok) throw Error(data.error || 'Permintaan gagal');
      for (const service of data.services) {
        const row = document.createElement('li');
        row.textContent = service.name + (service.enabled ? ' · aktif saat boot ' : ' · nonaktif saat boot ');
        if (service.mutable) {
          const button = document.createElement('button');
          button.type = 'button';
          button.textContent = service.enabled ? 'Nonaktifkan saat boot' : 'Aktifkan saat boot';
          button.onclick = () => {
            if (sid === session && window.confirm(button.textContent + ' untuk ' + service.name + '?')) {
              load({name: service.name, expected: service.enabled ? '1' : '0', enabled: service.enabled ? '0' : '1'});
            }
          };
          row.append(button);
        }
        list.append(row);
      }
      message.textContent = args ? 'Pengaturan startup tersimpan.' : '';
    } catch (error) {
      if (sid === session) message.textContent = error.message;
    } finally {
      pending = false;
      read.disabled = false;
    }
  }
  read.addEventListener('click', () => load());
  window.VeciServices = {reset() { list.replaceChildren(); message.textContent = ''; }};
})();
