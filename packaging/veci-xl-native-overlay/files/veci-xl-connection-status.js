// VeCI XL: owner-initiated authentication and verified carrier quota view.
// API calls use the logged-in VeCI session. No browser-to-operator traffic.
export async function mountXlConnection(root, api) {
  const host = root.querySelector('#veci-xl-connection');
  if (!host) return;
  host.replaceChildren();
  const heading = document.createElement('strong');
  const details = document.createElement('p');
  const official = document.createElement('a');
  official.href = 'https://www.xl.co.id/id/myxl';
  official.target = '_blank';
  official.rel = 'noopener noreferrer';
  official.textContent = 'Cek sisa kuota di myXL resmi';
  official.setAttribute('aria-label', 'Buka myXL resmi di tab baru');
  const quota = document.createElement('div');
  const controls = document.createElement('div');
  controls.className = 'cellular-actions';
  const button = (text) => {
    const el = document.createElement('button');
    el.type = 'button'; el.className = 'button button-secondary';
    el.textContent = text;
    return el;
  };
  const refreshStatus = button('Refresh Status XL');
  const refreshQuota = button('Ambil Kuota XL');
  const logout = button('Putuskan Sesi XL');
  const login = document.createElement('div');
  const numberInput = document.createElement('input');
  numberInput.type = 'tel'; numberInput.inputMode = 'numeric';
  numberInput.autocomplete = 'off'; numberInput.placeholder = 'Nomor XL: 628xxxxxxxxx';
  numberInput.maxLength = 15; numberInput.setAttribute('aria-label', 'Nomor XL');
  const request = button('Kirim OTP');
  const otpWrap = document.createElement('div');
  const otpInput = document.createElement('input');
  otpInput.type = 'text'; otpInput.inputMode = 'numeric';
  otpInput.autocomplete = 'one-time-code'; otpInput.placeholder = 'Kode OTP';
  otpInput.maxLength = 8; otpInput.setAttribute('aria-label', 'Kode OTP XL');
  const submit = button('Verifikasi OTP');
  login.append(numberInput, request, otpWrap);
  otpWrap.append(otpInput, submit);
  controls.append(refreshStatus, refreshQuota, logout);
  host.append(heading, details, official, quota, login, controls);
  const say = (title, description) => {
    heading.textContent = title; details.textContent = description;
  };
  const formatBytes = n => (n / 1073741824).toFixed(2) + ' GiB';
  const validBucket = b => b && typeof b.label === 'string' &&
    b.label.length > 0 && b.label.length <= 100 &&
    Number.isSafeInteger(b.remaining_bytes) && b.remaining_bytes >= 0 &&
    (!Object.hasOwn(b, 'total_bytes') ||
      (Number.isSafeInteger(b.total_bytes) && b.total_bytes >= b.remaining_bytes)) &&
    (!Object.hasOwn(b, 'expires_at') ||
      (typeof b.expires_at === 'string' && Number.isFinite(Date.parse(b.expires_at))));
  let busy = false;
  const buttons = [refreshStatus, refreshQuota, logout, request, submit];
  const disable = value => { for (const b of buttons) b.disabled = value; };
  const state = { configured: false, session: 'not_connected', https: false };
  async function load() {
    if (busy) return;
    busy = true; disable(true); quota.replaceChildren();
    login.hidden = true; refreshQuota.hidden = true; logout.hidden = true;
    say('Memeriksa koneksi XL…', 'Tidak mengirim OTP atau menghubungi operator.');
    try {
      const s = await api.call('veci.xl', 'status', {}, { timeout: 5000 });
      if (!s || typeof s.session !== 'string' ||
        typeof s.operator_configured !== 'boolean' || typeof s.https_only !== 'boolean') {
        throw Error('invalid_status');
      }
      state.configured = s.operator_configured;
      state.session = s.session;
      state.https = s.https_only;
      if (!s.https_only) {
        say('XL: HTTPS diperlukan', 'Autentikasi hanya tersedia melalui koneksi VeCI HTTPS.');
        return;
      }
      if (!s.operator_configured) {
        say('XL: konfigurasi operator belum tersedia',
          'Login native belum aktif. Gunakan myXL resmi untuk melihat kuota operator, tanpa membagikan OTP atau token ke router.');
        return;
      }
      logout.hidden = (s.session === 'not_connected');
      if (s.session !== 'verified') {
        if (s.session === 'pending_profile') {
          say('XL: verifikasi profil tertunda', 'Tidak mengirim ulang OTP secara otomatis.');
        } else {
          const waiting = s.session === 'otp_requested';
          say(waiting ? 'XL: menunggu OTP' : 'XL: belum terhubung',
            waiting ? 'Masukkan kode OTP yang Anda terima.' : 'Masukkan nomor XL milik Anda untuk mulai login.');
          login.hidden = false;
          otpWrap.hidden = !waiting;
          numberInput.hidden = waiting;
          request.hidden = waiting;
        }
        return;
      }
      refreshQuota.hidden = false;
      say('XL: akun terverifikasi', 'Membaca cache kuota operator.');
      const q = await api.call('veci.quota', 'status', {}, { timeout: 5000 });
      const t = Date.parse(q && q.fetched_at);
      const age = Date.now() - t;
      if (!q || (q.provider !== 'xl' && q.operator !== 'xl') ||
        q.source !== 'operator' || q.state !== 'ok' ||
        !Array.isArray(q.buckets) || q.buckets.length < 1 ||
        q.buckets.length > 30 || !Number.isFinite(age) ||
        age < 0 || age > 1800000 || !q.buckets.every(validBucket)) {
        if (Number.isFinite(age) && age > 1800000 &&
          q?.source === 'operator' && q.state === 'ok') {
          say('XL: cache kedaluwarsa', 'Tekan Ambil Kuota XL untuk meminta data terbaru.');
        } else {
          say('XL: kuota resmi belum tersedia',
            'Belum ada saldo operator yang valid di router. Cek melalui myXL resmi bila diperlukan.');
        }
        return;
      }
      say('XL: kuota operator', 'Data: ' + new Date(t).toLocaleString('id-ID'));
      const list = document.createElement('ul');
      for (const b of q.buckets) {
        const li = document.createElement('li');
        li.textContent = b.label + ': ' + formatBytes(b.remaining_bytes) +
          (Number.isSafeInteger(b.total_bytes) ? ' / ' + formatBytes(b.total_bytes) : '') +
          (typeof b.expires_at === 'string' ?
            ' · berlaku sampai ' + new Date(b.expires_at).toLocaleDateString('id-ID') : '');
        list.append(li);
      }
      quota.append(list);
    } catch {
      say('XL: status tidak tersedia', 'Gagal membaca status XL menggunakan sesi VeCI.');
    } finally {
      busy = false; disable(false);
    }
  }
  const errors = {
    otp_cooldown: 'Tunggu minimal 3 menit sebelum meminta OTP kembali.',
    operator_config_unavailable: 'Konfigurasi operator belum tersedia.',
    https_only_required: 'HTTPS diperlukan.',
    invalid_number: 'Format nomor XL tidak valid.',
    invalid_otp: 'Format kode OTP tidak valid.',
    otp_verification_failed: 'OTP tidak dapat diverifikasi.',
    quota_refresh_failed: 'Kuota operator belum dapat diperbarui.',
    action_in_progress: 'Permintaan sebelumnya masih berlangsung.'
  };
  async function action(method, data) {
    if (busy || !state.https || !state.configured) return;
    busy = true; disable(true);
    try {
      const r = await api.call('veci.xl', method, data, { timeout: 25000 });
      if (!r || r.ok !== true) {
        say('XL: permintaan belum berhasil',
          errors[r?.reason] || 'Backend menolak permintaan. Tidak mencoba otomatis.');
        return;
      }
      if (method === 'requestOtp') {
        numberInput.value = '';
        say('XL: OTP diminta', 'Periksa pesan OTP lalu masukkan kodenya.');
        otpWrap.hidden = false; numberInput.hidden = true; request.hidden = true;
        return;
      }
      if (method === 'submitOtp') otpInput.value = '';
      // Successful owner-initiated action; recheck actual account/cache status.
    } catch {
      say('XL: permintaan gagal', 'Koneksi ke backend VeCI terputus atau tidak merespons.');
      return;
    } finally {
      busy = false; disable(false);
    }
    await load();
  }
  refreshStatus.addEventListener('click', () => { void load(); });
  request.addEventListener('click', () => {
    const number = numberInput.value.trim();
    if (!/^62[0-9]{8,13}$/.test(number)) {
      say('XL: format nomor salah', 'Gunakan 62 diikuti nomor, sepanjang 10–15 digit.');
      return;
    }
    void action('requestOtp', { number });
  });
  submit.addEventListener('click', () => {
    const otp = otpInput.value.trim();
    if (!/^[0-9]{4,8}$/.test(otp)) {
      say('XL: format OTP salah', 'Masukkan 4–8 angka dari pesan operator.');
      return;
    }
    // Remove the OTP from the visible form before dispatching the request.
    otpInput.value = '';
    void action('submitOtp', { otp });
  });
  refreshQuota.addEventListener('click', () => {
    if (state.session === 'verified') void action('refreshQuota', {});
  });
  logout.addEventListener('click', async () => {
    if (busy || !window.confirm('Hapus token dan cache sesi XL lokal router ini?')) return;
    busy = true; disable(true); quota.replaceChildren();
    say('XL: memutuskan sesi…', 'Penghapusan lokal, tidak mencabut token pada operator.');
    try {
      const r = await api.call('veci.xl', 'logout', {}, { timeout: 8000 });
      if (r?.ok !== true || r.state !== 'not_connected') {
        throw Error('logout_failed');
      }
      numberInput.value = ''; otpInput.value = '';
    } catch {
      say('XL: logout gagal', 'Sesi belum dikonfirmasi terputus. Tekan Refresh Status XL.');
      busy = false; disable(false);
      return;
    }
    busy = false; disable(false);
    await load();
  });
  await load();
}
