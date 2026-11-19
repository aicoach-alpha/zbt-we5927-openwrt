'use strict';
(() => {
  const panels = ['startup', 'addon'].map(id => ({
    read: el(id + '-read'), list: el(id + '-services'), message: el(id + '-status'), addons: id === 'addon'
  }));
  let pending = false;
  async function load(panel, args) {
    const {read, list, message, addons} = panel;
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
        if (addons && !service.package) continue;
        const row = document.createElement('li');
        row.textContent = (addons ? service.package : service.name) + (service.enabled ? ' · aktif saat boot ' : ' · nonaktif saat boot ');
        if (service.mutable) {
          const button = document.createElement('button');
          button.type = 'button';
          button.textContent = service.enabled ? 'Nonaktifkan saat boot' : 'Aktifkan saat boot';
          button.onclick = () => {
            if (sid === session && window.confirm(button.textContent + ' untuk ' + service.name + '?')) {
              load(panel, {name: service.name, expected: service.enabled ? '1' : '0', enabled: service.enabled ? '0' : '1'});
            }
          };
          row.append(button);
        }
        list.append(row);
      }
      message.textContent = args ? 'Pengaturan startup tersimpan.' :
        addons && !list.childElementCount ? 'Tidak ada layanan DDNS atau SQM yang terpasang.' : '';
    } catch (error) {
      if (sid === session) message.textContent = error.message;
    } finally {
      pending = false;
      read.disabled = false;
    }
  }
  for (const panel of panels) panel.read.addEventListener('click', () => load(panel));
  window.VeciServices = {reset() {
    for (const panel of panels) {
      panel.list.replaceChildren();
      panel.message.textContent = '';
    }
  }};
})();
