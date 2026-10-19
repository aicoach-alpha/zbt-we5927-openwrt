// VeCI Cellular: owner-session XL readiness, no operator requests or secrets.
export async function mountXlConnection(root, api) {
  const host = root.querySelector('#veci-xl-connection');
  if (!host) return;
  host.replaceChildren();
  const title = document.createElement('strong');
  const detail = document.createElement('p');
  const refresh = document.createElement('button');
  refresh.type = 'button';
  refresh.className = 'button button-secondary';
  refresh.textContent = 'Refresh Status XL';
  host.append(title, detail, refresh);
  let busy = false;
  const show = (head, explanation) => {
    title.textContent = head;
    detail.textContent = explanation;
  };
  async function load() {
    if (busy) return;
    busy = true;
    refresh.disabled = true;
    show('Memeriksa status XL…', 'Tidak menghubungi operator atau meminta OTP.');
    try {
      const status = await api.call('veci.xl', 'status', {}, { timeout: 5000 });
      if (!status || typeof status !== 'object' || typeof status.session !== 'string' ||
          typeof status.operator_configured !== 'boolean' || typeof status.https_only !== 'boolean') {
        throw new Error('invalid_status');
      }
      if (!status.https_only) {
        show('XL: HTTPS diperlukan', 'Autentikasi tidak dapat dijalankan sebelum HTTPS tersedia.');
      } else if (!status.operator_configured) {
        show('XL: konfigurasi operator belum tersedia',
          'Komponen backend terpasang, tetapi parameter operator belum diprovisikan. Jangan meminta OTP.');
      } else if (status.session === 'verified') {
        show('XL: identitas akun terverifikasi',
          'Status kuota: ' + String(status.quota_status || 'belum tersedia') + '. Tidak sama dengan bukti saldo operator.');
      } else if (status.session === 'pending_profile') {
        show('XL: menunggu verifikasi profil', 'Sesi belum dapat dipakai sebagai bukti kuota operator.');
      } else if (status.session === 'otp_requested') {
        show('XL: menunggu verifikasi OTP', 'OTP hanya boleh dikirim lewat alur yang dimulai pengguna.');
      } else {
        show('XL: belum terhubung', 'Konfigurasi tersedia, tetapi sesi operator belum terverifikasi.');
      }
    } catch {
      show('XL: status tidak tersedia', 'Sesi VeCI mungkin belum mempunyai izin baca status XL.');
    } finally {
      busy = false;
      refresh.disabled = false;
    }
  }
  refresh.addEventListener('click', () => { void load(); });
  await load();
}
