'use strict';
(() => {
  const button = el('backup-export'), message = el('backup-message');
  // Two-phase configuration restore; never apply before an authenticated
  // archive-inspect response, binding the SHA256 and the current session.
  const restoreFile = el('backup-restore-file');
  const inspectButton = el('backup-restore-check');
  const applyButton = el('backup-restore-apply');
  const restoreMessage = el('backup-restore-message');
  let inspected = null;
  const digestOf = async data => Array.from(new Uint8Array(
    await crypto.subtle.digest('SHA-256', data)),
    byte => byte.toString(16).padStart(2,'0')).join('');
  restoreFile.onchange = () => {
    inspected = null;
    applyButton.disabled = true;
    restoreMessage.textContent = '';
  };
  const restoreRequest = async (phase, ticket) => {
    if (!sid || !restoreFile.files?.length) throw Error('Pilih arsip cadangan terlebih dahulu.');
    const session = sid;
    const archive = await restoreFile.files[0].arrayBuffer();
    if (!archive.byteLength || archive.byteLength > 2097152) throw Error('Ukuran arsip tidak didukung.');
    const digest = await digestOf(archive);
    if (phase === 'apply' && (!ticket || !inspected || digest !== inspected.digest ||
                               session !== inspected.session))
      throw Error('Arsip/sesi berubah. Inspeksi ulang diperlukan.');
    const meta = new TextEncoder().encode(session + digest + (ticket || ''));
    const body = new Uint8Array(meta.length + archive.byteLength);
    body.set(meta);
    body.set(new Uint8Array(archive), meta.length);
    const response = await fetch('/cgi-bin/veci2-restore?' + phase, {
      method:'POST', credentials:'omit', cache:'no-store',
      headers:{'Content-Type':'application/octet-stream'}, body
    });
    const result = await response.json();
    if (sid !== session) throw Error('Sesi login berubah, ulangi inspeksi.');
    if (!response.ok || !result.ok) throw Error(result.error || ('HTTP ' + response.status));
    return {session,digest,result};
  };
  inspectButton.onclick = async () => {
    if (inspectButton.disabled) return;
    inspected = null;
    applyButton.disabled = true;
    inspectButton.disabled = true;
    restoreMessage.textContent = 'Memeriksa arsip di router…';
    try {
      const verified = await restoreRequest('inspect','');
      inspected = {session:verified.session,digest:verified.digest,
                   ticket:verified.result.ticket};
      restoreMessage.textContent = 'Arsip lolos inspeksi format dan identitas board. Belum diterapkan.';
      applyButton.disabled = false;
    } catch (error) { restoreMessage.textContent = 'Inspeksi ditolak: ' + error.message; }
    finally {inspectButton.disabled = false;}
  };
  applyButton.onclick = async () => {
    if (!inspected || applyButton.disabled || inspected.session !== sid) return;
    if (!window.confirm('RESTORE akan mengganti konfigurasi sistem. Router mungkin kehilangan koneksi dan memerlukan reboot manual. Lanjutkan?')) return;
    const old = inspected;
    applyButton.disabled = true;
    restoreMessage.textContent = 'Menjalankan restore konfigurasi…';
    try {
      const verified = await restoreRequest('apply',old.ticket);
      if (verified.digest !== old.digest) throw Error('Arsip berubah. Periksa ulang sebelum restore.');
      restoreMessage.textContent = verified.result.reboot_required
        ? 'Konfigurasi dipulihkan. Reboot manual diperlukan; uji konektivitas setelah reboot.'
        : 'Restore belum dikonfirmasi.';
    } catch (error) {
      restoreMessage.textContent = 'Restore gagal / belum terkonfirmasi: ' + error.message;
    } finally {inspected = null;}
  };
  button.onclick = async () => {
    const session = sid;
    if (!session || button.disabled) return;
    button.disabled = true;
    try {
      const result = await fetch('/cgi-bin/veci2-backup', {method:'POST', cache:'no-store', credentials:'omit',
        headers:{'Content-Type':'application/octet-stream'}, body:session});
      if (!result.ok) throw Error('Ekspor gagal (HTTP ' + result.status + ').');
      const data = await result.arrayBuffer();
      const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', data)),
        byte => byte.toString(16).padStart(2, '0')).join('');
      if (digest !== result.headers.get('X-Archive-SHA256')) throw Error('Checksum arsip tidak cocok.');
      if (sid !== session) return;
      const url = URL.createObjectURL(new Blob([data], {type:'application/gzip'}));
      const link = document.createElement('a');
      link.href = url;
      link.download = 'VeCI-WE5927-config.tar.gz';
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
      message.textContent = 'Arsip konfigurasi · SHA-256 ' + digest;
    } catch (error) { if (sid === session) message.textContent = error.message; }
    finally { button.disabled = false; }
  };
})();
