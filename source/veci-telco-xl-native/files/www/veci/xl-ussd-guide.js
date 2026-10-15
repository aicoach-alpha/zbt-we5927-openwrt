import { VeciApi } from './js/lib/api.js';

// VeCI native optional XL *808# guided menu. No automatic dialing or replies.
// User-observed route hints, NOT asserted universally applicable by the carrier.
// A separate explicit confirmation is required before each modem transaction.
const api = new VeciApi();
const $ = (id) => document.getElementById(id);
const secure = () => window.location.protocol === 'https:';
const ROUTES = Object.freeze({ one: [7, 3, 2, 1], two: [7, 3, 2, 2] });
let route = null;
let index = 0;
let session = '';
let busy = false;
// Only known, non-sensitive RPC reason identifiers are shown in the browser.
// Never render raw backend/transport errors containing account or modem data.
const REASONS = Object.freeze({
  admin_required: 'Hak administrator USSD ditolak.',
  unavailable: 'Backend USSD tidak tersedia.',
  ussd_unavailable: 'Backend atau respons operator USSD tidak tersedia.',
  invalid_request: 'Permintaan USSD ditolak oleh validasi.',
  invalid_response: 'Respons modem atau RPC tidak sesuai format aman.',
  modem_busy: 'Modem sedang digunakan oleh proses lain.',
  modem_unavailable: 'Port serial modem tidak tersedia.',
  wrong_modem: 'Identitas atau port modem tidak cocok dengan pengaman perangkat.',
  sim_unverified: 'Identitas SIM aktif tidak dapat diverifikasi.',
  not_xl_network: 'Operator SIM aktif tidak cocok dengan pemeriksaan XL.',
  clock_unavailable: 'Jam router belum tersedia.',
  session_active: 'Masih ada sesi USSD lain yang aktif.',
  session_expired: 'Sesi USSD sudah kedaluwarsa.',
  step_limit: 'Batas langkah menu USSD sudah tercapai.',
  token_unavailable: 'Sistem tidak dapat membuat pengenal sesi aman.',
  outcome_unknown: 'Hasil perintah USSD tidak pasti. Jangan mencoba ulang otomatis.',
  network_rejected: 'Operator menolak permintaan USSD.',
  serial_unavailable: 'Komunikasi serial modem gagal.',
  state_invalid: 'Status sesi USSD tidak valid.',
  wrong_router: 'Router tidak cocok dengan target USSD.',
  wrong_board: 'Model router tidak cocok.',
  approval_required: 'Konfirmasi pilihan menu belum diberikan.',
  quota_unavailable: 'Kuota belum tersedia.'
});
function failure(answer) {
  const reason = answer && typeof answer.reason === 'string' && Object.hasOwn(REASONS, answer.reason)
    ? answer.reason : 'rpc_transport_or_permission';
  return new Error(reason);
}
function report(value) { $('guide-feedback').textContent = value; }
function invalidate() {
  session = '';
  route = null;
  index = 0;
  $('guide-menu').hidden = true;
}
function renderMenu(answer) {
  if (!answer || answer.ok !== true || answer.source !== 'operator_ussd') {
    throw new Error('Tidak ada respons USSD XL yang valid.');
  }
  $('guide-response').textContent = answer.text_supported && typeof answer.text === 'string'
    ? answer.text.slice(0, 768) : 'Balasan operator tidak dapat ditampilkan sebagai teks.';
  if (answer.interactive === true &&
      answer.text_supported === true &&
      /^[0-9a-f]{24}$/.test(String(answer.session || ''))) {
    session = answer.session;
    $('guide-menu').hidden = false;
    if (index < route.length) {
      $('guide-next').textContent = 'Pilihan yang diusulkan: ' + route[index] +
        ' (langkah ' + (index + 1) + ' dari ' + route.length + '). Periksa menu asli di atas.';
      $('guide-send').hidden = false;
    } else {
      $('guide-next').textContent = 'Jalur selesai, tetapi operator masih meminta pilihan lain. Lanjutkan secara manual dari Cellular.';
      $('guide-send').hidden = true;
    }
  } else {
    session = '';
    $('guide-menu').hidden = false;
    $('guide-next').textContent = 'Sesi selesai atau respons tidak interaktif. Jangan menganggapnya kuota terverifikasi kecuali teks XL menyebutkan sisa kuota.';
    $('guide-send').hidden = true;
  }
}
async function call(name, payload) {
  return api.call('veci.ussd', name, payload, { timeout: 37000 });
}
// Browser-side checks use read-only cached status and ubus access introspection.
// No start/reply/cancel call, modem interaction or account data is needed.
async function diagnoseRpc() {
  const output = $('guide-rpc-diagnostic');
  if (!output || !secure() || !api.sessionId) return;
  const button = $('guide-rpc-check');
  if (button) button.disabled = true;
  output.textContent = 'Memeriksa akses VeCI dan RPC USSD tanpa mengirim USSD…';
  let core = 'unavailable';
  let cached = 'unavailable';
  let access = 'unknown';
  try {
    const result = await api.call('veci.xl', 'status', {}, { timeout: 7000 });
    if (result && typeof result.https_only === 'boolean') core = 'reachable';
  } catch {
    core = 'unavailable';
  }
  try {
    const result = await api.call('veci.ussd', 'quotaStatus', {}, { timeout: 7000 });
    if (result && result.ok === true) cached = 'reachable';
    else if (result && result.ok === false) cached = 'returned_failure';
  } catch {
    cached = 'rpc_or_access_failure';
  }
  try {
    const result = await api.call('session', 'access', {
      ubus_rpc_session: api.sessionId, scope: 'ubus',
      object: 'veci.ussd', function: 'start'
    }, { timeout: 7000 });
    if (result && (result.access === true || result.access === 1)) access = 'allowed';
    else if (result && (result.access === false || result.access === 0)) access = 'denied';
  } catch {
    access = 'unknown';
  }
  output.textContent = 'VeCI RPC: ' + core +
    ' | USSD status RPC: ' + cached +
    ' | Izin start: ' + access +
    '. Tidak ada perintah USSD yang dikirim.';
  if (button) button.disabled = false;
}
function installRpcCheckButton() {
  if ($('guide-rpc-check')) return;
  const box = $('guide-action');
  if (!box) return;
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'button button-secondary';
  button.id = 'guide-rpc-check';
  button.textContent = 'Periksa akses RPC (tanpa USSD)';
  const output = document.createElement('p');
  output.id = 'guide-rpc-diagnostic';
  output.setAttribute('role', 'status');
  output.setAttribute('aria-live', 'polite');
  box.appendChild(button);
  box.appendChild(output);
  button.addEventListener('click', () => { void diagnoseRpc(); });
}
async function guarded(work) {
  if (busy) return;
  busy = true;
  for (const id of ['guide-route-one', 'guide-route-two', 'guide-send', 'guide-cancel']) {
    $(id).disabled = true;
  }
  try { await work(); }
  catch (err) {
    const reason = err && typeof err.message === 'string' ? err.message : '';
    const text = Object.hasOwn(REASONS, reason)
      ? REASONS[reason] : 'RPC USSD tidak merespons, izin ditolak, atau koneksi gagal.';
    report('USSD gagal: ' + text + ' Tidak dilakukan pengulangan otomatis.');
    invalidate();
  }
  finally {
    busy = false;
    for (const id of ['guide-route-one', 'guide-route-two', 'guide-send', 'guide-cancel']) {
      $(id).disabled = false;
    }
  }
}
async function begin(which) {
  if (!secure() || !api.sessionId || session) return;
  const values = ROUTES[which];
  if (!values) return;
  if (!window.confirm(
    'Mulai sesi XL *808# sekarang? Langkah berikutnya hanya dikirim atas persetujuan terpisah. Menu XL dapat berubah dan beberapa pilihan mungkin berbayar.'
  )) return;
  await guarded(async () => {
    const answer = await call('start', {});
    if (!answer || answer.ok !== true) throw failure(answer);
    route = values;
    index = 0;
    renderMenu(answer);
    report('Sesi dimulai. Periksa isi menu dari operator sebelum setiap pilihan.');
  });
}
async function nextChoice() {
  if (!session || !route || index >= route.length || busy) return;
  const choice = String(route[index]);
  const menu = $('guide-response').textContent;
  if (!menu || menu.startsWith('Balasan operator tidak')) return;
  if (!window.confirm(
    'Apakah menu XL yang tampil BENAR-BENAR menunjukkan pilihan ' + choice +
    ' untuk informasi kuota (bukan beli, aktivasi, atau paket berbayar)? ' +
    'Kirim satu pilihan ini saja? Batalkan bila isi menu berubah.'
  )) return;
  await guarded(async () => {
    const oldSession = session;
    session = '';
    const answer = await call('reply', {
      session: oldSession, choice, approval: 'I_APPROVE_THIS_USSD_CHOICE'
    });
    if (!answer || answer.ok !== true) throw failure(answer);
    index += 1;
    renderMenu(answer);
    report('Pilihan ' + choice + ' dikirim sekali. Balasan XL harus diperiksa lagi.');
  });
}
async function cancel() {
  if (busy || !session) return;
  const oldSession = session;
  invalidate();
  await guarded(async () => {
    await call('cancel', { session: oldSession });
    report('Sesi USSD ditutup tanpa permintaan kuota atau pilihan tambahan.');
  });
}
async function init() {
  const signin = $('guide-signin');
  if (!secure()) {
    signin.hidden = true;
    report('Buka halaman ini melalui HTTPS; jangan memasukkan kredensial di HTTP.');
    return;
  }
  $('guide-route-one').addEventListener('click', () => { void begin('one'); });
  $('guide-route-two').addEventListener('click', () => { void begin('two'); });
  $('guide-send').addEventListener('click', () => { void nextChoice(); });
  $('guide-cancel').addEventListener('click', () => { void cancel(); });
  $('guide-login').addEventListener('click', async () => {
    const username = $('guide-user').value.trim();
    const passwordField = $('guide-password');
    const password = passwordField.value;
    if (!username || username.length > 64 || !password) {
      passwordField.value = '';
      report('Masukkan akun administrator VeCI yang valid.');
      return;
    }
    $('guide-login').disabled = true;
    try {
      await api.login(username, password);
      if (!(await api.validateSession())) throw new Error('session_invalid');
      signin.hidden = true;
      $('guide-action').hidden = false;
      installRpcCheckButton();
      $('guide-user').value = '';
      report('VeCI terautentikasi. Pilih salah satu jalur XL.');
    } catch {
      report('Login VeCI gagal. Tidak ada USSD yang dikirim.');
    } finally {
      passwordField.value = '';
      $('guide-login').disabled = false;
    }
  });
  if (api.sessionId && (await api.validateSession().catch(() => false))) {
    signin.hidden = true;
    $('guide-action').hidden = false;
    installRpcCheckButton();
    report('VeCI terautentikasi. Pilih jalur XL untuk mulai.');
  } else {
    signin.hidden = false;
    $('guide-action').hidden = true;
    report('Masuk ke VeCI untuk menggunakan USSD.');
  }
}
window.addEventListener('pagehide', () => {
  invalidate();
  $('guide-user').value = '';
  $('guide-password').value = '';
  $('guide-response').textContent = '';
});
void init();
