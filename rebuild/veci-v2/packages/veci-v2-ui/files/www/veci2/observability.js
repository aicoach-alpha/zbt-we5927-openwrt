'use strict';
(() => {
  const button = document.getElementById('obs-24x7-read');
  const output = document.getElementById('obs-24x7-result');
  if (!button || !output) return;
  let busy = false;
  button.addEventListener('click', async () => {
    if (busy || !sid) return;
    const session = sid;
    busy = true;
    button.disabled = true;
    output.textContent = 'Membaca histori kesehatan sistem…';
    try {
      const result = await rpc('veci.v2.observability','status',{},session);
      if (session !== sid) return;
      if (!result.ok) throw Error(result.error || 'Health collector unavailable');
      if (result.telemetry !== 'collected' || !result.sample) {
        output.textContent = 'Monitoring: ' + (result.telemetry || 'unavailable') +
          '. Belum ada bukti data yang valid.';
        return;
      }
      const sample = result.sample;
      output.textContent = 'Kondisi jalur lokal: ' + (sample.state || 'unknown') +
        ', SIM/LTE carrier: ' + sample.usb0_carrier +
        ', rute LTE: ' + sample.lte_default_route +
        ', memori tersedia: ' + sample.memory_available_kib + ' KiB' +
        ', peringatan: ' + (sample.alert || 'none') +
        '. UAT perangkat fisik: belum dilakukan.';
    } catch (error) {
      if (session === sid) output.textContent = 'Monitoring belum terkonfirmasi: ' + error.message;
    } finally {
      busy = false;
      button.disabled = false;
    }
  });
  globalThis.VeciObservability = {reset() {output.textContent = '';button.disabled = false;}};
})();
