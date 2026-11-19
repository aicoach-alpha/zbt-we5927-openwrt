'use strict';
globalThis.VeciAccess = (() => {
  let generation = 0;
  let revision = '';
  function reset() {
    ++generation;
    revision = '';
    el('access-fields').disabled = true;
    el('access-read').disabled = false;
    el('access-status').textContent = el('access-idle').value = '';
  }
  async function run(method) {
    const session = sid;
    const args = {};
    if (method !== 'status') {
      if (!revision) return;
      args.revision = revision;
      if (method === 'setIdle') args.seconds = el('access-idle').value;
      if (!window.confirm('Simpan konfigurasi akses untuk startup layanan berikutnya?')) return;
    }
    const request = ++generation;
    const status = el('access-status');
    revision = '';
    el('access-fields').disabled = el('access-read').disabled = true;
    try {
      const data = await rpc('veci.v2.access', method, args, session);
      if (request !== generation || sid !== session) return;
      if (!data.ok) throw Error(data.error || 'Konfigurasi tidak tersedia');
      revision = data.revision;
      el('access-idle').value = data.idle || '0';
      status.textContent = (method === 'status' ? '' : 'Tersimpan untuk startup layanan berikutnya. ') +
        'SSH ' + (data.ssh_interface || 'default') + ' port ' + (data.ssh_port || '22') +
        ' · Password SSH ' + (data.ssh_password || 'default') + ' · Password root ' +
        (data.root_password || 'default') + ' · HTTPS ' + (data.listen_https || 'belum dikonfigurasi') +
        ' · Pengalihan HTTP ' + (data.redirect_https || 'default');
      el('access-fields').disabled = false;
    } catch (error) {
      if (request === generation && session === sid) status.textContent = error.message;
    } finally {
      if (request === generation) el('access-read').disabled = false;
    }
  }
  document.addEventListener('DOMContentLoaded', () => {
    el('access-read').addEventListener('click', () => run('status'));
    el('access-save').addEventListener('click', () => run('setIdle'));
    el('access-https').addEventListener('click', () => run('requireHttps'));
  });
  return {reset};
})();
