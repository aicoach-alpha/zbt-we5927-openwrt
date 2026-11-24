'use strict';
(() => {
  const form = el('route-form'), fields = el('route-fields'), list = el('route-list'), message = el('route-message');
  let revision = '', sequence = 0;
  const keys = ['name','kind','prefix','table','interface','gateway','priority'];
  async function request(method, args = {}) {
    const session = sid, current = ++sequence;
    if (!session) return;
    fields.disabled = true;
    el('route-read').disabled = true;
    list.replaceChildren();
    try {
      const data = await rpc('veci.v2.routes', method, {...args, revision}, session);
      if (session !== sid || current !== sequence) return;
      if (!data.ok) throw Error(data.error);
      revision = data.revision;
      for (const row of data.entries) {
        const item = document.createElement('li');
        item.textContent = [row.section, row.kind, row.target || row.src, row.dest, row.gateway, row.interface,
          'tabel ' + (row.table || row.lookup || 'default'), row.priority].filter(Boolean).join(' · ');
        if (row.editable) {
          const name = row.section.slice('veci2_route_'.length);
          const edit = document.createElement('button'), remove = document.createElement('button');
          edit.type = remove.type = 'button';
          edit.textContent = 'Edit';
          edit.onclick = () => {
            const values = {...row, name, prefix:row.target || row.src, table:row.table || row.lookup};
            for (const key of keys) form.elements[key].value = values[key] || '';
          };
          remove.textContent = 'Hapus';
          remove.onclick = () => { if (window.confirm('Hapus ' + name + ' untuk startup berikutnya?')) request('remove', {name}); };
          item.append(edit,remove);
        }
        list.append(item);
      }
      fields.disabled = false;
      message.textContent = method === 'status' ? '' : 'Tersimpan untuk startup berikutnya.';
    } catch (error) {
      if (session === sid && current === sequence) message.textContent = error.message;
    } finally {
      if (current === sequence) el('route-read').disabled = false;
    }
  }
  el('route-read').onclick = () => request('status');
  form.onsubmit = event => {
    event.preventDefault();
    if (window.confirm('Simpan preferensi routing untuk startup berikutnya?')) {
      request('save', Object.fromEntries(keys.map(key => [key, form.elements[key].value.trim()])));
    }
  };
  globalThis.VeciRoutes = {reset() {
    ++sequence; revision = ''; form.reset(); fields.disabled = true; list.replaceChildren();
    message.textContent = ''; el('route-read').disabled = false;
  }};
})();
