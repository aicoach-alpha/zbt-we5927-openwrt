'use strict';
(() => {
  const field = key => document.getElementById('dhcp-' + key);
  let state, owner, busy = false;
  function selectLease() {
    const lease = state.leases.find(row => row.section === field('section').value) || {};
    for (const key of ['name', 'mac', 'ip']) field(key).value = lease[key] || '';
    field('delete').disabled = !lease.section;
  }
  async function run(method, args = {}) {
    if (busy) return;
    const session = sid;
    busy = true;
    field('edit').disabled = true;
    try {
      if (!session) throw Error('Masuk terlebih dahulu');
      if (method !== 'status') {
        if (owner !== session || !state) throw Error('Baca kembali konfigurasi');
        const result = await rpc('veci.v2.dhcp', method, { ...args, revision: state.revision }, session);
        if (!result.ok) throw Error(result.error);
      }
      const data = await rpc('veci.v2.dhcp', 'status', {}, session);
      if (sid !== session) throw Error('Sesi berubah');
      if (!data.ok) throw Error(data.error);
      state = data;
      owner = session;
      for (const key of ['start', 'limit', 'time']) field(key).value = data[key];
      field('section').replaceChildren(new Option('Reservasi baru', ''));
      for (const row of data.leases) field('section').add(new Option([row.name,row.ip,row.mac].filter(Boolean).join(' · '), row.section));
      selectLease();
      field('servers').textContent = data.servers.join(', ');
      field('edit').disabled = false;
      field('msg').textContent = method === 'status' ? 'Konfigurasi terbaca' : method === 'apply' ? 'dnsmasq dimuat ulang' : 'Tersimpan. Pilih Terapkan untuk memuat ulang dnsmasq.';
    } catch (e) {
      state = undefined;
      field('msg').textContent = e.message;
    } finally { busy = false; }
  }
  const values = keys => Object.fromEntries(keys.map(k => [k, field(k).value.trim()]));
  field('section').onchange = selectLease;
  field('read').onclick = () => run('status');
  field('pool').onclick = () => run('savePool', values(['start','limit','time']));
  field('lease').onclick = () => run('saveLease', values(['section','mac','name','ip']));
  field('delete').onclick = () => { if (window.confirm('Hapus reservasi yang dipilih?')) run('deleteLease', values(['section'])); };
  for (const op of ['add','remove']) field(op).onclick = () => run('changeDns', {op, ...values(['server'])});
  field('apply').onclick = () => { if (window.confirm('Muat ulang dnsmasq pada router?')) run('apply', {confirm:'APPLY_DNSMASQ'}); };
})();
