'use strict';
(() => {
  const fields = el('cron-fields'), read = el('cron-read'), job = el('cron-job');
  const message = el('cron-status'), schedule = el('cron-schedule'), enabled = el('cron-enabled');
  const save = el('cron-save'), remove = el('cron-remove'), task = el('cron-task');
  let state, generation = 0;
  function select() {
    const current = state?.jobs.find(item => item.row === job.value);
    schedule.value = current?.schedule || '';
    enabled.checked = current ? current.enabled : true;
    save.disabled = remove.disabled = !current;
  }
  async function run(method) {
    const session = sid, request = ++generation;
    if (!session || (method !== 'status' && !state)) return;
    const args = {};
    if (method !== 'status') args.revision = state.revision;
    if (method === 'save' || method === 'remove') args.row = job.value;
    if (method === 'add') args.task = task.value;
    if (method === 'add' || method === 'save') {
      args.schedule = schedule.value.trim();
      args.enabled = enabled.checked ? '1' : '0';
    }
    fields.disabled = read.disabled = true;
    try {
      const data = await rpc('veci.v2.cron', method, args, session);
      if (sid !== session || generation !== request) return;
      if (!data.ok) throw Error(data.error);
      state = data;
      job.replaceChildren(...data.jobs.map(item => new Option('#' + item.row + ' · ' + item.label, item.row)));
      if (method === 'save') job.value = args.row;
      if (method === 'add') job.value = data.jobs[data.jobs.length - 1].row;
      select();
      fields.disabled = false;
      message.textContent = method === 'status' ? (data.jobs.length ? '' : 'Belum ada tugas terjadwal.') : 'Jadwal tersimpan.';
    } catch (error) {
      if (sid === session && generation === request) { state = null; message.textContent = error.message; }
    } finally { if (generation === request) read.disabled = false; }
  }
  job.onchange = select;
  read.onclick = () => run('status');
  el('cron-add').onclick = () => {
    if (schedule.reportValidity() && window.confirm('Tambah tugas dengan jadwal ini?')) run('add');
  };
  remove.onclick = () => {
    if (window.confirm('Hapus tugas terpilih dari jadwal router?')) run('remove');
  };
  el('cron-form').onsubmit = event => {
    event.preventDefault();
    if (window.confirm('Simpan perubahan jadwal tugas ini?')) run('save');
  };
  globalThis.VeciCron = {reset() {
    ++generation; state = null; fields.disabled = true; read.disabled = false;
    job.replaceChildren(); select(); message.textContent = '';
  }};
})();
