'use strict';
(() => {
  const button = el('backup-export'), message = el('backup-message');
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
