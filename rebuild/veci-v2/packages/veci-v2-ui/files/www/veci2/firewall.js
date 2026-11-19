'use strict';
(() => {
  const item = name => document.getElementById('fw-' + name);
  let model, generation = 0;
  function reset() {
    generation++;
    model = null;
    item('edit').disabled = true;
    item('read').disabled = false;
    item('message').textContent = '';
    for (const key of ['rule', 'zone']) item(key).replaceChildren();
    for (const key of ['ip', 'ext', 'port']) item(key).value = '';
  }
  function selectZone() {
    const zone = model?.zone.find(row => row.section === item('zone').value);
    for (const key of ['input', 'output', 'forward']) item(key).value = zone?.[key] || '';
    item('masq').checked = zone?.masq === '1';
    item('zone-save').disabled = !zone;
  }
  function setKind() {
    for (const key of ['ext', 'port', 'proto']) item(key).disabled = item('kind').value === 'dmz';
  }
  async function run(method, params = {}) {
    const session = sid;
    if (!session) return;
    const current = ++generation;
    item('read').disabled = item('edit').disabled = true;
    try {
      if (method !== 'status') {
        const result = await rpc('veci.v2.firewall', method, {...params, revision:model.revision}, session);
        if (!result.ok) throw Error(result.error);
      }
      const data = await rpc('veci.v2.firewall', 'status', {}, session);
      if (current !== generation || session !== sid) return;
      if (!data.ok) throw Error(data.error);
      model = data;
      item('zone').replaceChildren(...data.zone.map(z => new Option(z.name + ' · ' + z.network, z.section)));
      item('rule').replaceChildren(...data.redirect.map(r => new Option(
        [r.name || r.section, r.src, r.src_dport || '*', '→', r.dest_ip || r.dest, r.dest_port || '*'].join(' '), r.section)));
      item('delete').disabled = !data.redirect.length;
      selectZone();
      item('edit').disabled = false;
      item('message').textContent = method === 'status' ? '' : 'Tersimpan untuk startup firewall berikutnya.';
    } catch (error) {
      if (current === generation && session === sid) item('message').textContent = error.message;
    } finally { if (current === generation) item('read').disabled = false; }
  }
  for (const key of ['input', 'output', 'forward'])
    item(key).replaceChildren(...['ACCEPT','REJECT','DROP'].map(v => new Option(v, v)));
  item('zone').onchange = selectZone;
  item('kind').onchange = setKind;
  item('read').onclick = () => run('status');
  item('zone-save').onclick = () => {
    if (confirm('Simpan kebijakan zona? Setelah firewall dimulai ulang, kebijakan ini dapat memutus akses atau membuka akses masuk.'))
      run('setZone', {section:item('zone').value, input:item('input').value, output:item('output').value,
        forward:item('forward').value, masq:item('masq').checked ? '1' : '0', confirm:'SAVE_ZONE'});
  };
  item('delete').onclick = () => {
    if (confirm('Hapus aturan pengalihan terpilih?'))
      run('deleteRedirect', {section:item('rule').value, confirm:'DELETE_REDIRECT'});
  };
  item('add').onclick = () => {
    const dmz = item('kind').value === 'dmz';
    if (confirm(dmz ? 'Alihkan semua port WAN yang belum cocok dengan aturan lain ke host LAN ini?' : 'Buka port dari WAN ke host LAN ini?'))
      run('addRedirect', {kind:item('kind').value, ip:item('ip').value.trim(), proto:dmz ? 'all' : item('proto').value,
        ext:dmz ? '' : item('ext').value, port:dmz ? '' : item('port').value, confirm:dmz ? 'SAVE_ALL_PORTS_TO_HOST' : 'SAVE_FORWARD'});
  };
  window.VeciFirewall = {reset};
})();
