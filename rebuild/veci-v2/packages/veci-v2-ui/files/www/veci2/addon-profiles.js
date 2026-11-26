'use strict';
(() => {
  const button = document.getElementById('addon-profiles-read');
  const list = document.getElementById('addon-profiles-list');
  const output = document.getElementById('addon-profiles-status');
  if (!button || !list || !output) return;
  let busy = false;
  async function refresh(action, expected, objectMethod = 'setVpnStartup') {
    if (!sid || busy) return;
    const session = sid;
    busy = true; button.disabled = true;
    list.replaceChildren();
    output.textContent = 'Memeriksa addon…';
    try {
      if (action) {
        const ack = await rpc('veci.v2.addon',objectMethod,{action,expected},session);
        if (!ack.ok) throw Error(ack.error || 'Gagal menyimpan startup');
      }
      const result = await rpc('veci.v2.addon','status',{},session);
      if (session !== sid) return;
      if (!result.ok) throw Error(result.error || 'Status addon tidak tersedia');
      for (const [key,name] of [['wireguard','WireGuard'],['guest','Guest Portal'],['voucher','Voucher']]) {
        const row = document.createElement('li');
        row.textContent = name + ': ' + (result[key] || 'unknown') +
          (key === 'guest' && ['enabled','disabled'].includes(result[key]) ?
            ' (konfigurasi startup, bukan status AP live)' : '');
        if (['guest','voucher'].includes(key) && ['enabled','disabled'].includes(result[key])) {
          const control = document.createElement('button');
          control.type = 'button';
          control.textContent = result[key] === 'enabled' ? 'Nonaktifkan' : 'Aktifkan';
          control.addEventListener('click', () => {
            if (session !== sid || !window.confirm(control.textContent + ' ' + name + '? Perubahan portal dapat memengaruhi konektivitas tamu.')) return;
            let command;
            if (key === 'guest') command = result[key] === 'enabled' ? 'DISABLE_PORTAL_AP' : 'ENABLE_PORTAL_AP';
            else command = result[key] === 'enabled' ? 'ALLOW_CLICK_THROUGH' : 'REQUIRE_VOUCHER';
            refresh(command,result[key],'setPortalStartup');
          });
          row.append(control);
        }
        if (key === 'wireguard' && ['enabled','disabled'].includes(result[key])) {
          const control = document.createElement('button');
          control.type = 'button';
          control.textContent = result[key] === 'enabled' ? 'Nonaktifkan startup' : 'Aktifkan startup';
          control.addEventListener('click', () => {
            if (session !== sid || !window.confirm(control.textContent + ' WireGuard saat boot berikutnya?')) return;
            refresh(result[key] === 'enabled' ? 'DISABLE_WIREGUARD_NEXT_BOOT' : 'ENABLE_WIREGUARD_NEXT_BOOT',result[key]);
          });
          row.append(control);
        }
        list.append(row);
      }
      output.textContent = 'Perubahan startup tersimpan tanpa restart radio/network. ' +
        'Guest AP dan isolasi memerlukan verifikasi runtime setelah aktivasi terpisah.';
    } catch (error) {
      if (session === sid) output.textContent = error.message;
    } finally { busy = false; button.disabled = !sid; }
  }
  button.addEventListener('click', () => refresh());
  globalThis.VeciAddonProfiles = {reset() { list.replaceChildren(); output.textContent = ''; }};
})();
