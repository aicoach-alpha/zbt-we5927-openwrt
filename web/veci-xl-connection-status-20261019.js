// Native XL status for existing authenticated VeCI session.
// Read-only, does not request OTP or expose account secrets.
export async function mountXlConnection(root, api) {
  const host = root.querySelector('#veci-xl-connection');
  if (!host) return;
  const show = (title, detail) => {
    host.replaceChildren();
    const h = document.createElement('strong');
    h.textContent = title;
    const p = document.createElement('p');
    p.textContent = detail;
    host.append(h, p);
  };
  show('XL: memeriksa koneksi…', 'Tidak mengirim permintaan ke operator.');
  try {
    const r = await api.call('veci.xl', 'status', {}, { timeout: 5000 });
    if (!r || r.https_only !== true) {
      show('XL: koneksi belum aman', 'HTTPS diperlukan sebelum autentikasi.');
    } else if (r.operator_configured !== true) {
      show('XL: konfigurasi belum tersedia', 'Backend siap, tetapi kredensial integrasi operator belum dikonfigurasi. OTP belum dapat digunakan.');
    } else if (r.session === 'verified') {
      show('XL: akun terverifikasi', 'Status kuota: ' + (r.quota_status || 'belum tersedia') + '.');
    } else {
      show('XL: ' + String(r.session || 'not_connected'), 'Konfigurasi tersedia. Autentikasi operator harus dilakukan secara eksplisit.');
    }
  } catch {
    show('XL: status tidak tersedia', 'Periksa izin akses veci.xl pada sesi VeCI.');
  }
}
