'use strict';
(() => {
  const check = el('ussd-check'), form = el('ussd-form'), cancel = el('ussd-cancel');
  const status = el('ussd-status'), input = el('ussd-code');
  let slot, generation = 0;
  function reset() {
    generation++;
    slot = undefined;
    check.disabled = false;
    cancel.hidden = form.hidden = true;
    input.value = status.textContent = '';
  }
  async function act(method) {
    if (!sid || check.disabled) return;
    const session = sid;
    const args = {};
    if (method !== 'status') {
      if (![1,2].includes(slot)) return;
      if (method === 'send') {
        const code = input.value.trim();
        if (!/^[*#][0-9*#]{1,30}#$/.test(code) || !/[0-9]/.test(code)) {
          status.textContent = 'Gunakan kode operator dengan angka, * dan #.'; return;
        }
        if (!window.confirm('Kirim ke operator melalui SIM ' + slot + '? Tarif atau perubahan layanan operator dapat berlaku.')) return;
        args.code = code;
        args.confirm = 'SEND_USSD_ONCE';
      } else {
        if (!window.confirm('Akhiri sesi USSD pada SIM ' + slot + '?')) return;
        args.confirm = 'CANCEL_USSD';
      }
      args.slot = String(slot);
    }
    reset();
    const token = generation;
    check.disabled = true;
    try {
      const result = await rpc('veci.v2.ussd', method, args, session, 20000);
      if (sid !== session || token !== generation) return;
      if (!result.ok) throw Error(result.error);
      if (method === 'status') {
        slot = result.slot;
        form.hidden = !result.available || result.pending;
        cancel.hidden = !result.available || !result.pending;
        status.textContent = 'SIM ' + slot + (result.pending ? ' · Ada sesi tertunda.' :
          result.available ? ' · Modem mendukung USSD.' : ' · Dukungan USSD belum terkonfirmasi.');
      } else if (method === 'send') {
        status.textContent = result.response + ' · Baca status sebelum tindakan berikutnya.';
      } else status.textContent = 'Sesi diakhiri.';
    } catch (err) {
      if (sid === session && token === generation) status.textContent = err.message + ' · Periksa status modem.';
    } finally { if (token === generation) check.disabled = false; }
  }
  check.onclick = () => act('status');
  form.onsubmit = event => { event.preventDefault(); act('send'); };
  cancel.onclick = () => act('cancel');
  globalThis.VeciUssd = {reset};
})();
