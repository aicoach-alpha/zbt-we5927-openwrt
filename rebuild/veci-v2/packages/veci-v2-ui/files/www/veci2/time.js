'use strict';
let timeRequest = 0;
let timeSaving = false;
let timeRevision = '';
async function refreshTime(save = false) {
  if (timeSaving) return;
  const request = ++timeRequest;
  const session = sid;
  const fields = el('time-fields');
  const message = el('time-status');
  const args = save ? {
    enabled: el('time-enabled').checked ? '1' : '0',
    dhcp: el('time-dhcp').checked ? '1' : '0',
    servers: el('time-peers').value.trim(),
    zone: el('time-zone').value,
    revision: timeRevision
  } : {};
  if (save && !window.confirm('Simpan konfigurasi waktu dan NTP untuk startup berikutnya?')) return;
  timeSaving = save;
  fields.disabled = true;
  try {
    const result = await rpc('veci.v2.time', save ? 'save' : 'status', args, session);
    if (request !== timeRequest || sid !== session) return;
    if (!result.ok) throw Error(result.error || 'Konfigurasi tidak tersedia');
    timeRevision = result.revision;
    el('time-enabled').checked = result.enabled;
    el('time-dhcp').checked = result.dhcp;
    el('time-peers').value = result.servers;
    el('time-zone').value = 'keep';
    fields.disabled = false;
    message.textContent = (save ? 'Tersimpan untuk startup berikutnya. ' : '') +
      result.clock + ' · Zona tersimpan: ' + (result.zone || 'default sistem');
  } catch (err) {
    if (request === timeRequest && sid === session) message.textContent = err.message;
  } finally {
    if (request === timeRequest) timeSaving = false;
  }
}
document.addEventListener('DOMContentLoaded', () => {
  el('time-save').addEventListener('click', () => refreshTime(true));
  el('time-read').addEventListener('click', () => refreshTime());
});
globalThis.VeciTime = {reset() {
  ++timeRequest;
  timeSaving = false;
  timeRevision = '';
  el('time-fields').disabled = true;
  el('time-zone').value = 'keep';
  el('time-peers').value = el('time-status').textContent = '';
  el('time-enabled').checked = el('time-dhcp').checked = false;
}};
