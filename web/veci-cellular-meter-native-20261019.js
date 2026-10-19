// Native read-only Data Meter panel for VeCI Cellular. Shares VeciApi session.
export async function mountCellularMeter(root, api) {
  const host = root.querySelector('#veci-cellular-meter');
  if (!host) return;
  const fmt = value => Number.isSafeInteger(value) && value >= 0
    ? (value / 1000000000).toFixed(2) + ' GB' : '—';
  const render = (label, detail, extra) => {
    host.replaceChildren();
    const heading = document.createElement('h3');
    heading.textContent = label;
    const paragraph = document.createElement('p');
    paragraph.textContent = detail;
    const note = document.createElement('p');
    note.textContent = extra;
    host.append(heading, paragraph, note);
  };
  const load = async () => {
    render('Memuat pemakaian data…', 'Membaca counter modem.', 'Bukan kuota resmi operator.');
    try {
      const v = await api.call('veci.meter', 'status', {}, { timeout: 5000 });
      if (!v || v.carrier_authenticated !== false) throw Error('invalid_meter_status');
      if (v.state === 'needs_baseline') {
        render('Pemakaian modem', 'Download: ' + fmt(v.rx_bytes) + ' · Upload: ' + fmt(v.tx_bytes),
          'Counter sejak boot. Sisa kuota XL belum terverifikasi.');
      } else if (v.state === 'estimated' && Number.isSafeInteger(v.estimated_remaining_bytes)) {
        render('Estimasi pemakaian', 'Terpakai: ' + fmt(v.traffic_since_baseline_bytes) +
          ' · Sisa estimasi: ' + fmt(v.estimated_remaining_bytes),
          'Estimasi dari patokan manual, bukan saldo resmi operator.');
      } else {
        render('Data Meter', 'Status: ' + String(v.state || 'tidak tersedia'),
          'Sisa kuota resmi tidak tersedia.');
      }
    } catch {
      render('Data Meter belum tersedia', 'Tidak dapat membaca RPC dengan sesi VeCI aktif.',
        'Periksa izin sesi atau status service.');
    }
  };
  const refresh = root.querySelector('#veci-cellular-meter-refresh');
  if (refresh) refresh.addEventListener('click', () => { void load(); });
  await load();
}
