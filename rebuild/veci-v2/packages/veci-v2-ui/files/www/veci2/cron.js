'use strict';
(() => {
  const fields = el('cron-fields'), read = el('cron-read'), job = el('cron-job');
  const message = el('cron-status'), schedule = el('cron-schedule'), enabled = el('cron-enabled');
  let state, generation = 0;
  function select() {
    const current = state?.jobs.find(item => item.row === job.value);
    schedule.value = current?.schedule || '';
    enabled.checked = Boolean(current?.enabled);
  }
  async function run(save) {
    const session = sid, request = ++generation;
    if (!session || (save && !state)) return;
    const args = save ? {revision:state.revision, row:job.value, schedule:schedule.value.trim(),
      enabled:enabled.checked ? '1' : '0'} : {};
    fields.disabled = read.disabled = true;
    try {
      const data = await rpc('veci.v2.cron', save ? 'save' : 'status', args, session);
      if (sid !== session || generation !== request) return;
      if (!data.ok) throw Error(data.error);
      state = data;
      job.replaceChildren(...data.jobs.map(item => new Option('#' + item.row + ' · ' + item.label, item.row)));
      if (save) job.value = args.row;
      select();
      fields.disabled = !data.jobs.length;
      message.textContent = save ? 'Jadwal tersimpan.' : data.jobs.length ? '' : 'Tidak ada jadwal lima kolom yang dapat diedit.';
    } catch (error) {
      if (sid === session && generation === request) { state = null; message.textContent = error.message; }
    } finally { if (generation === request) read.disabled = false; }
  }
  job.onchange = select;
  read.onclick = () => run(false);
  el('cron-form').onsubmit = event => {
    event.preventDefault();
    if (window.confirm('Simpan perubahan jadwal tugas ini?')) run(true);
  };
  globalThis.VeciCron = {reset() {
    ++generation; state = null; fields.disabled = true; read.disabled = false;
    job.replaceChildren(); select(); message.textContent = '';
  }};
})();
