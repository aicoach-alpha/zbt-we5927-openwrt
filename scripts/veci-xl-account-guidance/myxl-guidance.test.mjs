import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { xlAccountGuidance, mountXlAccountGuidance } from './myxl-guidance.js';

test('only XL has a verified official URL; no fake router session', () => {
  const missing = xlAccountGuidance({ provider: 'xl', state: 'not_connected' });
  assert.equal(missing.available, true);
  assert.equal(missing.url, 'https://www.xl.co.id/id/myxl');
  assert.match(missing.explanation, /does not connect the account to VeCI/);
  const already = xlAccountGuidance({
    provider: 'xl', state: 'ready', source: 'carrier_authenticated'
  });
  assert.match(already.explanation, /verified local carrier cache/);
  for (const state of ['unauthorized', 'otp_required', 'stale', 'unavailable']) {
    assert.match(xlAccountGuidance({ provider: 'xl', state }).explanation,
      /does not connect/);
  }
  for (const provider of ['axis', 'telkomsel', null, '<script>', '__proto__']) {
    const x = xlAccountGuidance({ provider });
    assert.equal(x.available, false);
    assert.equal(x.url, null);
  }
});

test('native guidance uses DOM text, opens only official myXL, no input fields', () => {
  const prior = globalThis.document;
  const created = [];
  globalThis.document = {
    createElement(tag) {
      const node = {
        tag, children: [], attributes: {},
        setAttribute(k, v) { this.attributes[k] = v; },
        append(...nodes) { this.children.push(...nodes); },
        remove() { this.removed = true; }
      };
      created.push(node);
      return node;
    }
  };
  try {
    const panel = {
      node: null,
      querySelector() { return this.node; },
      appendChild(node) { this.node = node; }
    };
    const item = mountXlAccountGuidance(panel, { provider: 'xl', state: 'not_connected' });
    assert.equal(item, panel.node);
    assert.equal(item.attributes['data-official-xl-guidance'], 'true');
    const link = item.children.find(n => n.tag === 'a');
    assert.equal(link.href, 'https://www.xl.co.id/id/myxl');
    assert.equal(link.target, '_blank');
    assert.equal(link.rel, 'noopener noreferrer');
    assert.equal(link.referrerPolicy, 'no-referrer');
    assert.equal(created.filter(n => ['input', 'form', 'iframe'].includes(n.tag)).length, 0);
    assert.equal(mountXlAccountGuidance(panel, { provider: 'xl' }), item);
    assert.equal(mountXlAccountGuidance(panel, { provider: 'telkomsel' }), null);
    assert.equal(item.removed, true);
  } finally { globalThis.document = prior; }
});

test('source has no carrier authorization operations or secrets', () => {
  const source = fs.readFileSync(new URL('./myxl-guidance.js', import.meta.url), 'utf8');
  for (const bad of ['fetch(', 'XMLHttpRequest', 'AT+CMGR', 'AT+CUSD',
      'localStorage', 'sessionStorage', 'document.cookie', 'navigator.credentials',
      'access_token', 'client_secret', 'otpInput', 'phoneNumber',
      'api.myxl.xlaxiata.co.id', 'luci-static']) {
    assert.equal(source.includes(bad), false, bad);
  }
});
