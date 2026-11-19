'use strict';
(() => {
  const form = el('sim-lock-form'), read = el('sim-lock-read'), status = el('sim-lock-status');
  const code = el('sim-code'), nextPin = el('sim-new-pin');
  let selection, generation = 0;
  function reset() {
    ++generation;
    selection = null;
    read.disabled = false;
    form.hidden = true;
    code.value = nextPin.value = status.textContent = '';
  }
  read.onclick = async () => {
    reset();
    const token = generation, session = sid;
    if (!session) return;
    read.disabled = true;
    try {
      const data = await rpc('veci.v2.simlock', 'status', {}, session);
      if (token !== generation || sid !== session) return;
      if (!data.ok) throw Error(data.error);
      const mode = {pin:'PIN', puk:'PUK', ready:'Siap', unknown:'Tidak diketahui'}[data.mode];
      status.textContent = 'SIM ' + data.slot + ' · ' + mode +
        (data.mode === 'ready' ? '' : ' · Sisa percobaan: ' + (data.remaining ?? 'tidak diketahui'));
      if (!['pin','puk'].includes(data.mode) || !Number.isInteger(data.remaining) || data.remaining <= 1) return;
      selection = {slot:String(data.slot), mode:data.mode, remaining:String(data.remaining)};
      el('sim-code-label').textContent = mode;
      const puk = data.mode === 'puk';
      code.pattern = puk ? '[0-9]{8}' : '[0-9]{4,8}';
      nextPin.pattern = '[0-9]{4,8}';
      nextPin.disabled = el('sim-new-label').hidden = !puk;
      nextPin.required = puk;
      form.hidden = false;
    } catch (error) {
      if (token === generation && sid === session) status.textContent = error.message;
    } finally { if (token === generation) read.disabled = false; }
  };
  form.onsubmit = async event => {
    event.preventDefault();
    if (!selection || !sid || !form.reportValidity()) return;
    if (!window.confirm('Kirim sekali ke SIM ' + selection.slot + '? Kode yang salah mengurangi sisa percobaan.')) return;
    const args = {...selection, code:code.value, new_pin:nextPin.value, confirm:'UNLOCK_SIM_ONCE'};
    reset();
    const token = generation, session = sid;
    read.disabled = true;
    try {
      const result = await rpc('veci.v2.simlock', 'unlock', args, session);
      if (generation !== token || sid !== session) return;
      status.textContent = (result.ok ? 'Modem menerima perintah.' : 'Hasil: ' + result.error) + ' Baca status lagi.';
    } catch {
      if (generation === token && sid === session) status.textContent = 'Hasil belum diketahui. Baca status lagi.';
    } finally { if (generation === token) read.disabled = false; }
  };
  globalThis.VeciSimLock = {reset};
})();
