// Browser interaction regression using Node's built-in VM; no modem/network.
const fs = require('fs');
const vm = require('vm');
const assert = require('node:assert/strict');
const path = require('path');
const source = fs.readFileSync(
  path.join(__dirname, '../source/veci-ussd-dialer/files/www/veci/ussd-dialer.js'), 'utf8'
).replace(/^import[^\n]*\n/, '');
function makeElement(id = '') {
  return {
    id, textContent: '', value: '', hidden: false, disabled: false,
    listeners: {},
    children: [],
    addEventListener(name, cb) { this.listeners[name] = cb; },
    setAttribute() {},
    appendChild(child) { this.children.push(child); elements.set(child.id, child); }
  };
}
const elements = new Map();
for (const id of ['dial-login-panel','dial-panel','dial-feedback','dial-login','dial-code',
                 'dial-send','dial-reply','dial-cancel','dial-password','dial-user',
                 'dial-result','dial-response','dial-choice','dial-choice-wrap']) {
  elements.set(id, makeElement(id));
}
const calls = [];
class VeciApi {
  constructor() { this.sessionId = 'valid-existing-session'; }
  async validateSession() { return true; }
  async call(object, method, params) {
    assert.equal(object, 'session');
    assert.equal(method, 'access');
    assert.equal(params.scope, 'ubus');
    assert.equal(params.object, 'veci.dialer');
    assert.equal(params.function, 'start');
    assert.equal(Object.hasOwn(params, 'ubus_rpc_session'), false);
    return new Promise((resolve, reject) => calls.push({ resolve, reject }));
  }
}
const context = vm.createContext({
  VeciApi,
  document: {
    getElementById: id => elements.get(id) || null,
    createElement: () => makeElement()
  },
  window: {
    location: { protocol: 'https:' },
    addEventListener() {},
    confirm() { throw new Error('USSD must not be dialed by read-only tests'); }
  }
});
vm.runInContext(source, context, { filename: 'ussd-dialer.js' });
const settle = () => new Promise(resolve => setImmediate(resolve));
(async () => {
  await settle();
  const button = elements.get('dial-access-check');
  const status = elements.get('dial-access-result');
  assert.ok(button, 'permission button installed');
  assert.ok(status, 'permission status visible');
  assert.equal(calls.length, 0, 'must not auto-check on page load');
  assert.match(status.textContent, /belum diperiksa/);
  button.listeners.click();
  assert.equal(calls.length, 1);
  assert.match(status.textContent, /Pemeriksaan #1: menghubungi/);
  assert.equal(button.disabled, true);
  assert.match(elements.get('dial-feedback').textContent, /Memeriksa izin RPC/);
  button.listeners.click();
  assert.equal(calls.length, 1, 'double click must not duplicate request');
  calls[0].resolve({ access: true });
  await settle();
  assert.match(status.textContent, /Pemeriksaan #1 — Izin start: allowed/);
  assert.equal(button.disabled, false);
  button.listeners.click();
  assert.equal(calls.length, 2);
  assert.match(status.textContent, /Pemeriksaan #2: menghubungi/);
  const denied = new Error('session.access returned ubus status 6');
  denied.ubusStatus = 6;
  calls[1].reject(denied);
  await settle();
  assert.match(status.textContent, /Izin start: ubus_status_6/);
  assert.equal(button.disabled, false);
  button.listeners.click();
  calls[2].resolve({ access: false });
  await settle();
  assert.match(status.textContent, /Izin start: denied/);
  assert.equal(elements.get('dial-send').disabled, true);
  assert.equal(calls.length, 3);
  // Distinguish timeouts from unknown transport errors.
  const code = vm.runInContext("transportReason(new Error('session.access timed out'))", context);
  assert.equal(code, 'request_timeout');
  assert.equal(calls.filter(x => x.method === 'start').length, 0);
  console.log('VECI_USSD_PERMISSION_BUTTON_IMMEDIATE_FEEDBACK=pass');
  console.log('VECI_USSD_PERMISSION_BUTTON_DEBOUNCE_AND_NO_MODEM=pass');
  console.log('VECI_USSD_PERMISSION_BUTTON_DENIED_AND_TIMEOUT=pass');
})().catch(error => { console.error(error); process.exitCode = 1; });
