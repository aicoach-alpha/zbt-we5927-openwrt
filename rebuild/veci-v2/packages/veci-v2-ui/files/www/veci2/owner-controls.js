'use strict';
/* Standalone panels with authenticated ubus RPC and explicit destructive confirmations. */
(() => {
  const el = id => document.getElementById(id);
  let rpc, authenticated, epoch = 0, busy = false, simReady = false;
  const set = (id, value) => { const node = el(id); if (node) node.textContent = value; };
  const ip4 = value => {
    if (!/^(0|[1-9][0-9]{0,2})(\.(0|[1-9][0-9]{0,2})){3}$/.test(value)) return false;
    const a = value.split('.').map(Number);
    return a.every(n => n <= 255) && a[0] > 0 && a[0] < 224 && a[0] !== 127;
  };
  const mac = value => /^[a-f0-9]{2}(:[a-f0-9]{2}){5}$/i.test(value);
  const port = value => Number.isInteger(Number(value)) && Number(value) >= 1 &&
    Number(value) <= 65535 && /^[1-9][0-9]{0,4}$/.test(value);
  function optionList(id, values, label, placeholder) {
    const sel = el(id);
    sel.replaceChildren(new Option(placeholder, ''));
    for (const item of values) sel.add(new Option(label(item), item.name || String(item.index)));
  }
  async function call(object, method, args = {}, timeout = 11000) {
    if (!authenticated() || !rpc) throw Error('Login diperlukan');
    const response = await rpc(object, method, args, timeout);
    if (response.ok !== true) throw Error(String(response.error || 'Operasi gagal'));
    return response;
  }
  function resetAuth() {
    epoch++; busy = false; simReady = false;
    for (const id of ['owner-lease-status','owner-sim-status','owner-firewall-status','owner-ntp-status',
      'owner-system-summary','owner-system-log','owner-forward-list']) set(id, 'Login diperlukan.');
    el('owner-sim-submit').disabled = true;
    optionList('owner-forward-delete', [], () => '', 'Pilih port');
    optionList('owner-lease-delete', [], () => '', 'Pilih reservasi');
  }
  async function refreshNetwork() {
    if (!authenticated()) return;
    const seq = ++epoch;
    const results = await Promise.allSettled([
      call('veci.v2.sim', 'status'),
      call('veci.v2.dhcp', 'status')
    ]);
    if (seq !== epoch || !authenticated()) return;
    const sim = results[0];
    if (sim.status === 'fulfilled') {
      const s = sim.value;
      simReady = s.auto_failover === false && [1,2].includes(s.selector_slot);
      el('owner-sim-slot').value = String(s.selector_slot);
      el('owner-sim-submit').disabled = !simReady || busy;
      set('owner-sim-status', 'SIM terpilih: ' + s.selector_slot +
        ' · konfigurasi: ' + s.configured_slot +
        (s.auto_failover === false ? ' · failover otomatis off' : ' · failover aktif'));
    } else {
      simReady = false; el('owner-sim-submit').disabled = true;
      set('owner-sim-status', 'Status SIM belum terverifikasi: ' + sim.reason.message);
    }
    const lease = results[1];
    if (lease.status === 'fulfilled') {
      const list = Array.isArray(lease.value.leases) ? lease.value.leases : [];
      optionList('owner-lease-delete', list, x => [x.name || '', x.mac || '', x.ip || ''].filter(Boolean).join(' · '), 'Pilih reservasi');
      set('owner-lease-status', list.length + ' reservasi statis tersimpan');
    } else {
      set('owner-lease-status', 'Reservasi belum bisa dibaca: ' + lease.reason.message);
    }
  }
  async function refreshSettings(loadLogs = false) {
    if (!authenticated()) return;
    const seq = ++epoch;
    const results = await Promise.allSettled([
      call('veci.v2.firewall','status'),
      call('veci.v2.system','ntp'),
      call('veci.v2.system','observability'),
      call('veci.v2.system','leds'),
      ...(loadLogs ? [call('veci.v2.system','logs')] : [])
    ]);
    if (seq !== epoch || !authenticated()) return;
    if (results[0].status === 'fulfilled') {
      const f = results[0].value;
      const forwards = (Array.isArray(f.forwards) ? f.forwards : []).filter(x => typeof x.name === 'string');
      set('owner-forward-list', 'Aturan forwarding: ' + forwards.length +
        ' · kebijakan input WAN: ' + (f.wan_input || 'unknown'));
      optionList('owner-forward-delete',
        forwards.filter(x => /^veci_port_(tcp|udp)_[0-9]+$/.test(x.name)),
        x => x.name + ' · ' + x.destination, 'Pilih port');
      set('owner-firewall-status', 'Kebijakan WAN: ' + (f.wan_input || 'tidak terverifikasi'));
    } else set('owner-firewall-status', 'Firewall belum terverifikasi: ' + results[0].reason.message);
    if (results[1].status === 'fulfilled') {
      const servers = results[1].value.servers || [];
      el('owner-ntp-first').value = servers[0] || 'pool.ntp.org';
      el('owner-ntp-second').value = servers[1] || '';
      set('owner-ntp-status', 'Server NTP: ' + (servers.join(', ') || 'belum diatur'));
    } else set('owner-ntp-status','NTP belum terverifikasi: ' + results[1].reason.message);
    const obs = results[2].status === 'fulfilled' ? results[2].value : null;
    const leds = results[3].status === 'fulfilled' ? results[3].value : null;
    set('owner-system-summary', obs ?
      'Uptime ' + (obs.uptime_seconds || '?') + ' dtk · LTE ' + (obs.lte_link || '?') +
      ' · SSH ' + (obs.ssh_listening || '?') +
      ' · LED ' + (Array.isArray(leds?.leds) ? leds.leds.map(x=>x.name + ':' + x.brightness).join(', ') : 'belum terverifikasi') :
      'Observabilitas belum terverifikasi.');
    if (loadLogs) {
      const report = results[4];
      set('owner-system-log', report.status === 'fulfilled' ? String(report.value.logs || 'Tidak ada log.') :
        'Log tidak tersedia: ' + report.reason.message);
    }
  }
  async function invoke(button, output, object, method, args, timeout = 15000, refresh = null) {
    if (busy || !authenticated()) return;
    busy = true; button.disabled = true; set(output, 'Memproses permintaan…');
    try {
      await call(object, method, args, timeout);
      if (!authenticated()) return;
      set(output, 'Diterima oleh router. Periksa kondisi aktual.');
      if (refresh) await refresh();
    } catch (err) {
      if (authenticated()) set(output, 'Operasi gagal / belum terkonfirmasi: ' + err.message);
    } finally {
      busy = false;
      button.disabled = false;
      el('owner-sim-submit').disabled = !simReady || !authenticated();
    }
  }
  function init(send, auth) {
    rpc = send; authenticated = auth;
    el('owner-sim-form').addEventListener('submit', event => {
      event.preventDefault();
      const slot = Number(el('owner-sim-slot').value);
      if (!simReady || ![1,2].includes(slot)) return;
      if (!window.confirm('Ganti ke SIM' + slot + '? Modem akan restart dan koneksi LTE dapat putus beberapa menit.')) return;
      invoke(el('owner-sim-submit'),'owner-sim-status','veci.v2.sim','switchSim',
        {slot,confirmation:'SWITCH_SIM_' + slot},110000,refreshNetwork);
    });
    el('owner-lease-form').addEventListener('submit', event => {
      event.preventDefault();
      const data = {mac:el('owner-lease-mac').value.trim().toLowerCase(),
        ip:el('owner-lease-ip').value.trim(),name:el('owner-lease-name').value.trim()};
      if (!mac(data.mac) || !ip4(data.ip) || (data.name && !/^[A-Za-z0-9-]{1,32}$/.test(data.name))) {
        set('owner-lease-status','Alamat MAC, IP atau nama perangkat tidak valid.'); return;
      }
      if (!window.confirm('Simpan reservasi DHCP ' + data.ip + ' untuk ' + data.mac + '?')) return;
      invoke(event.submitter || el('owner-lease-form').querySelector('button'),
        'owner-lease-status','veci.v2.dhcp','add',data,15000,refreshNetwork);
    });
    el('owner-lease-delete-btn').addEventListener('click', event => {
      const value=el('owner-lease-delete').value;
      if (!/^(0|[1-9][0-9]{0,2})$/.test(value)) return;
      if (!window.confirm('Hapus reservasi DHCP pilihan? Perangkat mungkin menerima IP berbeda.')) return;
      invoke(event.currentTarget,'owner-lease-status','veci.v2.dhcp','delete',
        {index:Number(value),confirmation:'DELETE_LEASE_'+value},15000,refreshNetwork);
    });
    el('owner-forward-form').addEventListener('submit', event => {
      event.preventDefault();
      const from=el('owner-port-external').value.trim();
      const to=el('owner-port-internal').value.trim();
      const destination=el('owner-port-dest').value.trim();
      const protocol=el('owner-port-protocol').value;
      if (!port(from)||!port(to)||!ip4(destination)||!['tcp','udp'].includes(protocol)) {
        set('owner-firewall-status','Port atau alamat IP tujuan tidak valid.'); return;
      }
      if (!window.confirm('Buka port WAN ' + from + '/' + protocol + ' ke ' + destination +
        ':' + to + '? Perangkat tujuan akan dapat diakses dari internet jika operator mengizinkan.')) return;
      invoke(event.submitter || el('owner-forward-form').querySelector('button'),
        'owner-firewall-status','veci.v2.firewall','addForward',
        {from_port:Number(from),to_port:Number(to),destination,protocol,confirmation:'FORWARD_'+from},
        16000,refreshSettings);
    });
    el('owner-forward-delete-btn').addEventListener('click', event => {
      const name=el('owner-forward-delete').value;
      if (!/^veci_port_(tcp|udp)_[0-9]+$/.test(name)) return;
      if (!window.confirm('Hapus aturan ' + name + '?')) return;
      invoke(event.currentTarget,'owner-firewall-status','veci.v2.firewall','deleteForward',
        {name,confirmation:'DELETE_'+name},16000,refreshSettings);
    });
    el('owner-dmz-form').addEventListener('submit', event => {
      event.preventDefault();
      const destination=el('owner-dmz-dest').value.trim();
      if (!ip4(destination)) {set('owner-firewall-status','IP LAN tidak valid');return;}
      if (!window.confirm('BAHAYA: DMZ membuka hampir semua port inbound ke '+destination+'. Tetap aktifkan?')) return;
      invoke(event.submitter || el('owner-dmz-form').querySelector('button'),
        'owner-firewall-status','veci.v2.firewall','setDmz',
        {destination,confirmation:'ENABLE_DMZ_'+destination},16000,refreshSettings);
    });
    el('owner-dmz-disable').addEventListener('click', event => {
      if (!window.confirm('Nonaktifkan DMZ VeCI?')) return;
      invoke(event.currentTarget,'owner-firewall-status','veci.v2.firewall','setDmz',
        {destination:'DISABLE',confirmation:'DISABLE_DMZ'},16000,refreshSettings);
    });
    el('owner-ntp-form').addEventListener('submit', event => {
      event.preventDefault();
      const first=el('owner-ntp-first').value.trim(),second=el('owner-ntp-second').value.trim();
      const host=x=>/^[A-Za-z0-9][A-Za-z0-9.-]{0,252}$/.test(x)&&!x.includes('..')&&!x.endsWith('.');
      if (!host(first)||(second&&!host(second))||first===second) {
        set('owner-ntp-status','Server NTP tidak valid.');return;
      }
      if (!window.confirm('Simpan server NTP ' + first + '?')) return;
      invoke(event.submitter || el('owner-ntp-form').querySelector('button'),
        'owner-ntp-status','veci.v2.system','setNtp',
        {first,second,confirmation:'SET_NTP'},14000,refreshSettings);
    });
    el('owner-system-refresh').addEventListener('click',()=>refreshSettings(true));
  }
  globalThis.VeciOwnerControls={init,refreshNetwork,refreshSettings,logout:resetAuth};
})();
