'use strict';
(() => {
  const button = document.getElementById('watchdog-read');
  const output = document.getElementById('watchdog-result');
  if (!button || !output) return;
  let pending = false;
  button.addEventListener('click', async () => {
    if (pending || !sid) return;
    pending = true; button.disabled = true;
    const session = sid;
    output.textContent = 'Memeriksa status watchdog kernel…';
    try {
      const result = await rpc('veci.v2.watchdog', 'status', {}, session);
      if (session !== sid) return;
      if (!result.ok) throw Error(result.error || 'Status tidak tersedia');
      output.textContent = 'GPIO37: ' + result.registration + ' · Kernel: ' + result.kernel_state +
        ' (baca status, bukan uji watchdog fisik)';
    } catch (error) {
      if (session === sid) output.textContent = error.message;
    } finally {
      pending = false; button.disabled = !sid;
    }
  });
  globalThis.VeciWatchdog = {reset() { output.textContent = ''; button.disabled = false; }};
})();
