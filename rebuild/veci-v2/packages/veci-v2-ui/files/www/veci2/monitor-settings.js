'use strict';
(() => {
  const read = document.getElementById('monitor-read');
  const save = document.getElementById('monitor-save');
  const field = document.getElementById('monitor-interval');
  const result = document.getElementById('monitor-result');
  if (!read || !save || !field || !result) return;
  let current = null, busy = false;
  async function run(write = false) {
    if (!sid || busy) return;
    const value = Number(field.value);
    if (write && (!Number.isInteger(value) || value < 5 || value > 120 ||
        !window.confirm('Simpan interval monitor LTE tanpa restart modem?'))) return;
    busy = true; read.disabled = save.disabled = true;
    const session = sid;
    result.textContent = 'Memeriksa konfigurasi monitor…';
    try {
      const data = await rpc('veci.v2.lte',write ? 'setMonitor':'status',
          write ? {interval:String(value),expected:String(current)} : {},session);
      if (session !== sid) return;
      if (!data.ok) throw Error(data.error || 'Konfigurasi tidak dapat dibaca');
      current = data.monitor_interval;
      if (typeof current !== 'number' || current < 5 || current > 120)
        throw Error('Interval konfigurasi tidak valid');
      field.value = current;
      field.disabled = false; save.disabled = false;
      result.textContent = 'Interval tersimpan: ' + current + ' detik (aktif saat monitor membaca konfigurasi)';
    } catch (error) { if (session === sid) result.textContent = error.message; }
    finally { busy = false; read.disabled = !sid; }
  }
  read.addEventListener('click', () => run(false));
  save.addEventListener('click', () => run(true));
  globalThis.VeciMonitor = {reset() {
    current = null; field.disabled = save.disabled = true; result.textContent = '';
  }};
})();
