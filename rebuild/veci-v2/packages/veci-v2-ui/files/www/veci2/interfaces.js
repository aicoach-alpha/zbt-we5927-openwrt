'use strict';
(() => {
  const form = el('interface-form');
  const fields = form.elements;
  let revision = '';
  let owner = '';
  let pending = false;
  function toggleWan() {
    el('interface-static').disabled = fields.wan_mode.value !== 'static';
  }
  async function load(save) {
    const session = sid;
    if (pending || !session) return;
    if (save && (session !== owner || !revision)) {
      el('interface-message').textContent = 'Baca konfigurasi terlebih dahulu.';
      return;
    }
    const args = {};
    if (save) {
      for (const name of ['lan', 'lan_mask', 'wan_mode', 'wan', 'wan_mask', 'gateway']) args[name] = fields[name].value.trim();
      if (!confirm('Simpan untuk aktivasi jaringan berikutnya? Catat alamat LAN baru dan pastikan rentang DHCP serta reservasi tetap sesuai.')) return;
      Object.assign(args, {revision, confirm: 'SAVE_NETWORK'});
    }
    pending = true;
    fields.controls.disabled = true;
    try {
      const data = await rpc('veci.v2.interfaces', save ? 'save' : 'status', args, session);
      if (sid !== session) return;
      if (!data.ok) throw new Error(data.error);
      revision = data.revision;
      owner = session;
      for (const name of ['lan', 'lan_mask', 'wan_mode', 'wan', 'wan_mask', 'gateway']) fields[name].value = data[name];
      toggleWan();
      fields.controls.disabled = false;
      el('interface-message').textContent = save ? 'Tersimpan. Jaringan aktif tetap berjalan hingga aktivasi berikutnya.' : '';
    } catch (err) {
      revision = '';
      if (sid === session) el('interface-message').textContent = String(err.message);
    } finally { pending = false; }
  }
  globalThis.VeciInterfaces = {reset() {
    form.reset();
    revision = owner = '';
    fields.controls.disabled = true;
    el('interface-message').textContent = '';
  }};
  fields.wan_mode.addEventListener('change', toggleWan);
  el('interface-read').addEventListener('click', () => load(false));
  form.addEventListener('submit', event => { event.preventDefault(); load(true); });
})();
