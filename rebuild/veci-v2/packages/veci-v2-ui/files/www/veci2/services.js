'use strict';
(() => {
  const panels = ['startup', 'addon'].map(id => ({
    read: el(id + '-read'), list: el(id + '-services'), message: el(id + '-status'), addons: id === 'addon'
  }));
  let pending = false;
  async function load(panel, args, profileMethod = 'setVpnStartup') {
    const {read, list, message, addons} = panel;
    const session = sid;
    if (!session || pending) return;
    pending = true;
    read.disabled = true;
    list.replaceChildren();
    message.textContent = 'Memproses…';
    try {
      // Add-on profile actions belong to veci.v2.addon, NOT veci.v2.services.
      // Startup toggles continue using the sole service manager.
      const isProfileAction = Boolean(args?.action);
      let data = await rpc(isProfileAction ? 'veci.v2.addon' : 'veci.v2.services',
        isProfileAction ? profileMethod : args ? 'save' : 'status', args || {}, session);
      if (session !== sid) return;
      if (!data.ok) throw Error(data.error || 'Permintaan gagal');
      if (args?.action) {
        data = await rpc('veci.v2.services', 'status', {}, session);
        if (sid !== session) return;
        if (!data.ok) throw Error(data.error || 'Layanan tidak tersedia');
      }
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
      if (addons) {
        const profiles = await rpc('veci.v2.addon', 'status', {}, session);
        if (sid !== session) return;
        if (!profiles.ok) throw Error(profiles.error || 'Profil add-on tidak tersedia');
        const labels = {absent:'belum terpasang', unconfigured:'konfigurasi belum lengkap',
          enabled:'aktif di konfigurasi', disabled:'nonaktif di konfigurasi'};
        for (const [key, name] of [['wireguard','WireGuard'], ['guest','Guest portal'], ['voucher','Voucher']]) {
          const row = document.createElement('li');
          row.textContent = name + ' · ' + (labels[profiles[key]] || 'status belum diketahui');
          if (['enabled','disabled'].includes(profiles[key])) {
            const enabled = profiles[key] === 'enabled';
            const button = document.createElement('button');
            button.type = 'button';
            const actions = {
              wireguard: ['DISABLE_WIREGUARD_NEXT_BOOT','ENABLE_WIREGUARD_NEXT_BOOT'],
              guest: ['DISABLE_PORTAL_AP','ENABLE_PORTAL_AP'],
              voucher: ['ALLOW_CLICK_THROUGH','REQUIRE_VOUCHER']
            };
            button.textContent = key === 'voucher' ?
              (enabled ? 'Izinkan masuk tanpa voucher' : 'Wajibkan voucher') :
              (enabled ? 'Nonaktifkan saat boot' : 'Aktifkan saat boot');
            button.onclick = () => {
              const detail = key === 'voucher' && enabled ? ' Tamu dapat masuk cukup dengan konfirmasi di portal.' : '';
              if (sid === session && window.confirm(button.textContent + ' untuk ' + name + ' pada startup berikutnya?' + detail))
                load(panel, {expected:profiles[key], action:actions[key][enabled ? 0 : 1]},
                  key === 'wireguard' ? 'setVpnStartup' : 'setPortalStartup');
            };
            row.append(button);
          }
          list.append(row);
        }
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
