import { VeciApi } from './js/lib/api.js';
const api = new VeciApi();
const $ = id => document.getElementById(id);
const nice = n => Number.isSafeInteger(n) && n >= 0
  ? (n / 1000000000).toFixed(2) + ' GB' : 'Tidak diketahui';
function say(v) { $('meter-feedback').textContent = v; }
async function refresh() {
  $('meter-refresh').disabled = true;
  try {
    const result = await api.call('veci.meter', 'status', {}, { timeout: 5000 });
    if (!result || result.carrier_authenticated !== false) throw new Error('invalid_reply');
    if (result.state === 'estimated' &&
        Number.isSafeInteger(result.estimated_remaining_bytes) &&
        Number.isSafeInteger(result.traffic_since_baseline_bytes)) {
      $('meter-state').textContent = 'Estimasi berdasarkan pemakaian modem';
      $('meter-usage').textContent = 'Terpakai sejak patokan: ' + nice(result.traffic_since_baseline_bytes);
      $('meter-remaining').textContent = 'Sisa estimasi: ' + nice(result.estimated_remaining_bytes);
      say('Estimasi diperbarui. Saldo resmi tetap perlu dicek melalui operator.');
    } else if (result.state === 'needs_baseline') {
      $('meter-state').textContent = 'Pemakaian modem terbaca';
      $('meter-usage').textContent = 'Unduh sejak boot: ' + nice(result.rx_bytes) +
        ' · Unggah sejak boot: ' + nice(result.tx_bytes);
      $('meter-remaining').textContent = 'Sisa kuota belum tersedia: belum ada patokan operator.';
      say('Router dapat menghitung pemakaian; tidak ada saldo operator yang diklaim.');
    } else if (result.state === 'baseline_expired') {
      $('meter-state').textContent = 'Patokan kedaluwarsa';
      $('meter-usage').textContent = 'Interface/boot berubah atau patokan terlalu lama.';
      $('meter-remaining').textContent = 'Estimasi dinonaktifkan agar tidak menampilkan sisa yang keliru.';
    } else {
      $('meter-state').textContent = 'Data pemakaian tidak tersedia';
      $('meter-usage').textContent = 'Periksa kondisi koneksi modem.';
      $('meter-remaining').textContent = 'Tidak ada saldo operator yang ditampilkan.';
    }
  } catch { say('Tidak dapat membaca counter modem, tanpa permintaan ke operator.'); }
  finally { $('meter-refresh').disabled = false; }
}
async function save() {
  const v = Number($('meter-baseline').value);
  if (!Number.isSafeInteger(v) || v < 1 || v > 1048576) {
    say('Masukkan sisa kuota dalam MB, bilangan bulat antara 1 dan 1.048.576.');
    return;
  }
  if (!window.confirm('Simpan ' + v + ' MB sebagai patokan manual myXL? Ini bukan kuota yang telah diverifikasi oleh VeCI.')) return;
  $('meter-save').disabled = true;
  try {
    const r = await api.call('veci.meter', 'setBaseline', { remaining_mb: v }, { timeout: 7000 });
    if (r?.ok !== true || r.carrier_authenticated !== false) throw new Error('baseline_failed');
    $('meter-baseline').value = '';
    await refresh();
  } catch { say('Patokan tidak tersimpan. Tidak ada perubahan kuota operator.'); }
  finally { $('meter-save').disabled = false; }
}
async function ready() {
  $('meter-signin').hidden = true;
  $('meter-data').hidden = false;
  await refresh();
}
async function init() {
  if (location.protocol !== 'https:') {
    say('Buka halaman melalui HTTPS sebelum login administrator.');
    return;
  }
  $('meter-refresh').addEventListener('click', () => { void refresh(); });
  $('meter-save').addEventListener('click', () => { void save(); });
  $('meter-login').addEventListener('click', async () => {
    const user = $('meter-user').value.trim(), pass = $('meter-password').value;
    if (!user || !pass) { say('Masukkan akun administrator.'); return; }
    try {
      await api.login(user, pass);
      if (!(await api.validateSession())) throw new Error('unauthenticated');
      $('meter-user').value = '';
      await ready();
    } catch { say('Login VeCI gagal.'); }
    finally { $('meter-password').value = ''; }
  });
  if (api.sessionId && await api.validateSession().catch(() => false)) await ready();
}
window.addEventListener('pagehide', () => { $('meter-password').value = ''; $('meter-baseline').value = ''; });
void init();