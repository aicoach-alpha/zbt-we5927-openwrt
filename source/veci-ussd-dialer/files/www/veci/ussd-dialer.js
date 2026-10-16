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
  ussd_unavailable: 'Backend USSD tidak tersedia.'
});
function notice(text) { $('dial-feedback').textContent = text; }
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
    const label = Object.hasOwn(errorLabels, error?.message)
      ? errorLabels[error.message]
      : 'Transaksi gagal atau respons RPC tidak pasti. Tidak ada pengulangan otomatis.';
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
      $('dial-user').value = '';
      notice('Terhubung ke VeCI. Masukkan kode USSD pilihanmu.');
    } catch { notice('Login VeCI gagal. USSD tidak dikirim.'); }
    finally { passwordField.value = ''; $('dial-login').disabled = false; }
  });
  if (api.sessionId && await api.validateSession().catch(() => false)) {
    $('dial-login-panel').hidden = true;
    $('dial-panel').hidden = false;
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
