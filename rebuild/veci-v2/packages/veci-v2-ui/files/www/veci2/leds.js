'use strict';
(() => {
  const read = el('led-read'), list = el('led-list'), message = el('led-status');
  async function load(name) {
    const session = sid;
    if (!session || read.disabled) return;
    read.disabled = true;
    list.replaceChildren();
    message.textContent = 'Membaca panel…';
    try {
      const data = await rpc('veci.v2.leds', name ? 'identify' : 'status', name ? {name} : {}, session);
      if (sid !== session) return;
      if (!data.ok) throw Error(data.error || 'Gagal membaca LED');
      for (const led of data.leds) {
        const row = document.createElement('li');
        row.textContent = led.name + ' · ' + led.brightness + ' · ' + led.trigger + ' ';
        if (led.identify) {
          const pulse = document.createElement('button');
          pulse.type = 'button';
          pulse.textContent = 'Identifikasi selama 1 detik';
          pulse.onclick = () => { if (sid === session) load(led.name); };
          row.append(pulse);
        }
        list.append(row);
      }
      for (const key of data.buttons) {
        const row = document.createElement('li');
        row.textContent = 'Tombol ' + key.name + (key.handler ? ' · handler terpasang' : ' · handler belum tersedia');
        list.append(row);
      }
      message.textContent = list.children.length ? '' : 'Panel belum terdeteksi.';
    } catch (error) {
      if (sid === session) message.textContent = error.message;
    } finally {
      read.disabled = false;
    }
  }
  read.addEventListener('click', () => load());
  globalThis.VeciLeds = {reset() { list.replaceChildren(); message.textContent = ''; }};
})();
