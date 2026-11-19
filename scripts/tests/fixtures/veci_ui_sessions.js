'use strict';
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');

async function exercise(destroyCode) {
  const elements = new Map();
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      value: '', hidden: false, reset() {}, replaceChildren() {}, append() {},
      addEventListener(name, fn) { this[name] = fn; },
      querySelector(name) { return element(id + name); }
    });
    return elements.get(id);
  }
  const document = {
    getElementById: element, createElement: element, querySelectorAll: () => [],
    addEventListener(name, fn) { this[name] = fn; }
  };
  const zero = '0'.repeat(32), user = 'a'.repeat(32);
  const calls = [], alerts = [];
  let reloads = 0, reply;
  const location = {protocol: 'http:', hostname: 'router.home', reload() { reloads++; }};
  const context = vm.createContext({
    document, location, AbortController, setTimeout, clearTimeout,
    window: {alert: message => alerts.push(message)},
    VeciSmsCenter: {init() {}, logout() {}, activate() {}},
    fetch: async (url, options) => {
      assert.equal(url, '/ubus');
      const params = JSON.parse(options.body).params;
      calls.push(params);
      let result;
      if (params[2] === 'login') result = await new Promise(resolve => { reply = resolve; });
      else if (params[2] === 'destroy') result = [destroyCode];
      else result = [0, {}];
      return {ok: true, json: async () => ({result})};
    }
  });
  vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), context);
  document.DOMContentLoaded();
  element('username').value = 'observer';
  function submit() {
    element('password').value = 'test-fixture';
    return element('login-form').submit({preventDefault() {}});
  }
  await submit();
  assert.equal(calls.length, 0);
  location.protocol = 'https:';
  for (const bad of [[6], [0, {ubus_rpc_session: zero}], [0, {ubus_rpc_session: 123}]]) {
    const pending = submit();
    reply(bad);
    await pending;
    assert.equal(vm.runInContext('sid', context), '');
    assert.equal(element('password').value, '');
  }
  const pending = submit();
  await submit();
  assert.equal(calls.length, 4);
  assert.deepEqual(calls[3], [zero, 'session', 'login', {username:'observer', password:'test-fixture'}]);
  reply([0, {ubus_rpc_session:user, acls:{'access-group': {
    'veci-v2-runtime':['read'], 'other':['write'], 'veci-v2-sms-admin':['read','write']
  }}}]);
  await pending;
  assert.deepEqual(calls[4], [user, 'veci.v2', 'status', {}]);
  assert.equal(element('session-account').textContent, 'observer');
  assert.equal(element('session-permissions').textContent,
    'veci-v2-runtime (baca) · veci-v2-sms-admin (baca, tulis)');
  assert.equal(element('workspace').hidden, false);
  const logout = element('logout').click();
  assert.equal(vm.runInContext('sid', context), '');
  assert.equal(element('workspace').hidden, true);
  await submit();
  await logout;
  assert.equal(calls.length, 6);
  assert.deepEqual(calls[5], [user, 'session', 'destroy', {}]);
  assert.equal(element('session-account').textContent, '');
  assert.equal(element('session-permissions').textContent, '');
  assert.equal(reloads, 1);
  assert.equal(alerts.length, destroyCode ? 1 : 0);
}
(async () => {
  await exercise(0);
  await exercise(6);
})().catch(error => { console.error(error); process.exitCode = 1; });
