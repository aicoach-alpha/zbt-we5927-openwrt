'use strict';
/* Browser-side LTE Speed Test Lite. Explicit click only; no router CGIs,
 * no modem commands, no persistent client identifiers, no background tests. */
(() => {
  const ORIGIN = 'https://speed.cloudflare.com';
  const get = id => document.getElementById(id);
  let running = false;
  let controller = null;
  const history = [];
  function toMbps(bytes, ms) { return (bytes * 8 / (ms * 1000)).toFixed(2); }
  async function request(url, options = {}) {
    const response = await fetch(url, {
      mode: 'cors', credentials: 'omit', cache: 'no-store',
      referrerPolicy: 'no-referrer', signal: controller.signal, ...options
    });
    if (!response.ok) throw Error('HTTP ' + response.status);
    return response;
  }
  async function execute() {
    const timings = [];
    for (let i = 0; i < 4; i++) {
      const start = performance.now();
      const res = await request(ORIGIN + '/__down?bytes=64&r=' + i);
      await res.arrayBuffer();
      timings.push(performance.now() - start);
    }
    const latency = timings.reduce((sum, t) => sum + t, 0) / timings.length;
    const jitter = timings.slice(1).reduce((sum, t, i) => sum + Math.abs(t - timings[i]), 0) / (timings.length - 1);
    get('speedtest-result').textContent = 'Mengukur download…';
    const startDownload = performance.now();
    const res = await request(ORIGIN + '/__down?bytes=1048576');
    const bytes = (await res.arrayBuffer()).byteLength;
    const elapsedDownload = performance.now() - startDownload;
    if (bytes !== 1048576) throw Error('Respons download tidak lengkap');
    get('speedtest-result').textContent = 'Mengukur upload…';
    const body = new Uint8Array(524288);
    const startUpload = performance.now();
    await request(ORIGIN + '/__up', {
      method: 'POST', headers: {'Content-Type': 'application/octet-stream'}, body
    });
    const elapsedUpload = performance.now() - startUpload;
    return {
      down: toMbps(bytes, elapsedDownload), up: toMbps(body.byteLength, elapsedUpload),
      latency: latency.toFixed(1), jitter: jitter.toFixed(1)
    };
  }
  document.addEventListener('DOMContentLoaded', () => {
    const run = get('speedtest-run');
    const cancel = get('speedtest-cancel');
    const result = get('speedtest-result');
    const log = get('speedtest-history');
    if (!run || !cancel || !result) return;
    cancel.addEventListener('click', () => controller?.abort());
    run.addEventListener('click', async () => {
      if (running || get('workspace').hidden) return;
      running = true; run.disabled = true; cancel.disabled = false;
      controller = new AbortController();
      const kill = setTimeout(() => controller.abort(), 40000);
      result.textContent = 'Mengukur latensi HTTPS…';
      try {
        const data = await execute();
        const output = 'Download ' + data.down + ' Mbps · Upload ' + data.up +
          ' Mbps · Latensi HTTP ' + data.latency + ' ms · Jitter HTTP ' + data.jitter + ' ms';
        result.textContent = output;
        history.unshift(new Date().toLocaleTimeString('id-ID') + ' — ' + output);
        history.length = Math.min(history.length, 5);
        log.textContent = 'Riwayat sesi browser:\n' + history.join('\n');
      } catch (err) {
        result.textContent = controller.signal.aborted ? 'Tes dibatalkan atau batas waktu habis.' :
          'Tes gagal: ' + err.message;
      } finally {
        clearTimeout(kill); controller = null; running = false;
        run.disabled = false; cancel.disabled = true;
      }
    });
  });
})();
