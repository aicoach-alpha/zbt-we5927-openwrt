import { VeciApi } from './js/lib/api.js';

const api = new VeciApi();
const $ = id => document.getElementById(id);
const CODE = /^[*#][0-9*#]{1,30}#$/;
const CHOICE = /^(0|[1-9][0-9]?)$/;
const SESSION = /^[0-9a-f]{24}$/;
const secure = () => window.location.protocol === 'https:';
let activeSession = '';
let steps = 0;
let busy = false;
let interactionUnknown = false;
const errorLabels = Object.freeze({
  invalid_dial: 'Kode USSD tidak valid. Contoh *123#.',
  invalid_choice: 'Pilihan menu harus 0–99.',
  approval_required: 'Persetujuan tindakan belum diberikan.',
  modem_busy: 'Modem sedang digunakan. Tidak ada pengulangan otomatis.',
  modem_unavailable: 'Port modem tidak tersedia.',
  wrong_modem: 'Identitas modem tidak cocok.',
  sim_unverified: 'SIM aktif belum terverifikasi.',
  session_active: 'Ada sesi USSD lain yang masih berlangsung.',
  session_expired: 'Sesi operator telah kedaluwarsa.',
  step_limit: 'Batas langkah sesi tercapai.',
  outcome_unknown: 'Hasil permintaan ke modem tidak pasti. Jangan langsung mengulang.',
  network_rejected: 'Jaringan menolak kode USSD.',
  serial_unavailable: 'Komunikasi serial tidak tersedia.',
  invalid_response: 'Format respons modem tidak valid.',
  https_only_required: 'Administrasi router harus HTTPS-only.',
  ussd_unavailable: 'Backend USSD tidak tersedia.',
  admin_required: 'Hak administrator tidak tersedia.',
  unavailable: 'Layanan USSD belum siap.',
  wrong_router: 'Router tidak cocok dengan perangkat yang diizinkan.',
  clock_unavailable: 'Jam router tidak tersedia.',
  token_unavailable: 'Token sesi aman tidak dapat dibuat.',
  state_invalid: 'State sesi USSD tidak valid.',
  state_unavailable: 'State sesi USSD tidak dapat disimpan.',
  unsafe_path: 'Jalur state modem tidak aman.'
});
function transportReason(error) {
  if (Number.isInteger(error?.ubusStatus) && error.ubusStatus >= 1 && error.ubusStatus <= 20)
    return 'ubus_status_' + error.ubusStatus;
  const text = typeof error?.message === 'string' ? error.message : '';
  if (text === 'Not authenticated') return 'session_not_authenticated';
  if (/^veci\.dialer\.(?:start|reply|cancel|status) timed out$/.test(text) ||
      /^session\.access timed out$/.test(text)) return 'request_timeout';
  if (/^HTTP 4[0-9]{2}$/.test(text)) return 'http_4xx';
  if (/^HTTP 5[0-9]{2}$/.test(text)) return 'http_5xx';
  return 'transport_unknown';
}
function notice(text) { $('dial-feedback').textContent = text; }
// Router core 0.2.2's VeciApi.call exposes ubusStatus. Use only sanitized codes.
// HTTPS ubus binds the session identity itself: do not send session tokens in
// session.access parameters, and never store or log access responses.
let accessCheckInFlight = false;
let accessChecks = 0;
async function checkDialPermission() {
  // Important: visible feedback is set synchronously BEFORE the first await.
  // The read-only check never triggers start/reply/cancel or a modem command.
  const report = $('dial-access-result');
  const button = $('dial-access-check');
  if (!report || !button || accessCheckInFlight) return;
  accessCheckInFlight = true;
  accessChecks += 1;
  const sequence = accessChecks;
  button.disabled = true;
  button.textContent = 'Sedang memeriksa…';
  report.textContent = 'Pemeriksaan #' + sequence + ': menghubungi izin sesi router…';
  notice('Memeriksa izin RPC VeCI (tanpa mengirim USSD).');
  let status = 'unknown';
  try {
    const result = await api.call('session', 'access', {
      scope: 'ubus', object: 'veci.dialer', function: 'start'
    }, { timeout: 7000 });
    if (result?.access === true || result?.access === 1) status = 'allowed';
    else if (result?.access === false || result?.access === 0) status = 'denied';
    else status = 'no_access_field';
  } catch (error) {
    status = transportReason(error);
  } finally {
    report.textContent = 'Pemeriksaan #' + sequence + ' — Izin start: ' + status +
      ' (read-only; tidak ada USSD yang dikirim).';
    notice('Pemeriksaan izin selesai: ' + status + '.');
    button.textContent = 'Periksa izin Dial (tanpa USSD)';
    button.disabled = false;
    accessCheckInFlight = false;
  }
  if (status === 'denied') {
    $('dial-send').disabled = true;
    notice('Akses USSD ditolak untuk sesi ini. Login ulang untuk memuat izin terbaru.');
  }
  return status;
}
function installAccessCheck() {
  if ($('dial-access-result')) return;
  const output = document.createElement('p');
  output.id = 'dial-access-result';
  output.setAttribute('role', 'status');
  output.setAttribute('aria-live', 'polite');
  output.textContent = 'Izin dial belum diperiksa. Klik tombol di bawah untuk memeriksa tanpa USSD.';
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'button button-secondary';
  button.id = 'dial-access-check';
  button.textContent = 'Periksa izin Dial (tanpa USSD)';
  button.addEventListener('click', () => { void checkDialPermission(); });
  // Place the result next to the button, not at the bottom of a large panel.
  const panel = $('dial-panel');
  panel.appendChild(button);
  panel.appendChild(output);
}
function closeLocal() {
  activeSession = '';
  steps = 0;
  $('dial-reply').hidden = true;
  $('dial-cancel').hidden = true;
  $('dial-choice-wrap').hidden = true;
  $('dial-choice').value = '';
}
function setBusy(value) {
  busy = value;
  for (const id of ['dial-send', 'dial-reply', 'dial-cancel', 'dial-login'])
    $(id).disabled = value;
}
async function call(method, params) {
  return api.call('veci.dialer', method, params, { timeout: 37000 });
}
function readResponse(result) {
  if (!result || result.ok !== true || result.source !== 'operator_ussd') {
    const reason = result?.reason;
    throw new Error(Object.hasOwn(errorLabels, reason) ? reason : 'rpc_error');
  }
  $('dial-result').hidden = false;
  $('dial-response').textContent = result.text_supported && typeof result.text === 'string'
    ? result.text.slice(0, 768) : 'Balasan USSD diterima, tetapi format teks belum didukung.';
  if (result.interactive === true && result.text_supported === true &&
      SESSION.test(String(result.session || ''))) {
    activeSession = result.session;
    $('dial-choice-wrap').hidden = false;
    $('dial-reply').hidden = false;
    $('dial-cancel').hidden = false;
    notice('Menu interaktif diterima. Baca pilihan dari operator sebelum membalas.');
  } else {
    closeLocal();
    notice('Permintaan selesai, atau respons tidak mendukung menu interaktif.');
  }
}
async function perform(work) {
  if (busy || interactionUnknown) return;
  setBusy(true);
  try { await work(); }
  catch (error) {
    const code = Object.hasOwn(errorLabels, error?.message) ? error.message : transportReason(error);
    const label = Object.hasOwn(errorLabels, code) ? errorLabels[code]
      : code === 'ubus_status_6' ? 'Izin RPC ditolak (ubus status 6).'
      : code === 'ubus_status_7' ? 'RPC tidak valid atau timeout (ubus status 7).'
      : 'Transaksi ditolak atau hasil tidak pasti (' + code + '). Jangan ulangi otomatis.';
    interactionUnknown = true;
    closeLocal();
    notice('USSD gagal: ' + label + ' Muat ulang halaman sebelum memulai sesi baru.');
  } finally { setBusy(false); }
}
async function dial() {
  if (!secure() || !api.sessionId || activeSession || busy || interactionUnknown) return;
  const code = $('dial-code').value.trim();
  if (!CODE.test(code) || code.length > 32) {
    notice('Masukkan kode lengkap yang hanya menggunakan angka, * dan # (maksimal 32 karakter).');
    return;
  }
  if (!window.confirm('Kirim kode USSD ' + code + ' ke operator SIM aktif? Layanan USSD mungkin dikenakan biaya atau mengubah pengaturan.')) return;
  await perform(async () => {
    const response = await call('start', { code, approval: 'I_APPROVE_THIS_USSD_DIAL' });
    steps = 0;
    $('dial-code').value = '';
    readResponse(response);
  });
}
async function reply() {
  if (!activeSession || busy || interactionUnknown || steps >= 10) return;
  const choice = $('dial-choice').value.trim();
  if (!CHOICE.test(choice)) { notice('Pilihan menu harus 0–99.'); return; }
  if (!window.confirm('Kirim pilihan ' + choice + ' sesuai menu operator yang tampil? Pilihan ini dapat dikenakan biaya.')) return;
  await perform(async () => {
    const prior = activeSession;
    activeSession = '';
    const response = await call('reply', {
      session: prior, choice, approval: 'I_APPROVE_THIS_USSD_CHOICE'
    });
    steps += 1;
    $('dial-choice').value = '';
    readResponse(response);
  });
}
async function cancel() {
  if (!activeSession || busy) return;
  const prior = activeSession;
  closeLocal();
  setBusy(true);
  try {
    const response = await call('cancel', { session: prior });
    notice(response?.ok ? 'Sesi USSD ditutup.' : 'Sesi lokal ditutup. Hasil penutupan modem tidak pasti.');
  } catch { notice('Sesi lokal ditutup. Hasil penutupan modem tidak pasti.'); }
  finally { setBusy(false); }
}
async function init() {
  $('dial-send').addEventListener('click', () => { void dial(); });
  $('dial-reply').addEventListener('click', () => { void reply(); });
  $('dial-cancel').addEventListener('click', () => { void cancel(); });
  if (!secure()) { $('dial-login-panel').hidden = true; notice('Akses USSD hanya melalui HTTPS.'); return; }
  $('dial-login').addEventListener('click', async () => {
    const user = $('dial-user').value.trim();
    const passwordField = $('dial-password');
    const password = passwordField.value;
    if (!user || user.length > 64 || !password) {
      passwordField.value = '';
      notice('Masukkan kredensial administrator router.');
      return;
    }
    $('dial-login').disabled = true;
    try {
      await api.login(user, password);
      if (!(await api.validateSession())) throw new Error('invalid_session');
      $('dial-login-panel').hidden = true;
      $('dial-panel').hidden = false;
      installAccessCheck();
      $('dial-user').value = '';
      notice('Terhubung ke VeCI. Masukkan kode USSD pilihanmu.');
    } catch { notice('Login VeCI gagal. USSD tidak dikirim.'); }
    finally { passwordField.value = ''; $('dial-login').disabled = false; }
  });
  if (api.sessionId && await api.validateSession().catch(() => false)) {
    $('dial-login-panel').hidden = true;
    $('dial-panel').hidden = false;
    installAccessCheck();
    notice('Terhubung ke VeCI. Masukkan kode USSD pilihanmu.');
  }
}
window.addEventListener('pagehide', () => {
  closeLocal();
  $('dial-password').value = '';
  $('dial-code').value = '';
  $('dial-response').textContent = '';
});
void init();
