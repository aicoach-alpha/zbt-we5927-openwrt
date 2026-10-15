import test from 'node:test';
import assert from 'node:assert/strict';
import { summarizeOperatorQuota } from './native-quota.js';

const base = {
  schema: 1, provider: 'xl', state: 'ready', source: 'carrier_authenticated',
  total_bytes: 10 * 1024 ** 3, remaining_bytes: 4 * 1024 ** 3
};

test('only proven carrier aggregate is displayed', () => {
  const x = summarizeOperatorQuota(base);
  assert.equal(x.provider, 'XL');
  assert.equal(x.value, '4.00 GiB');
  assert.match(x.detail, /10.00 GiB/);
});

test('unverified and malformed responses never show quota numbers', () => {
  const broken = [
    {...base, source: 'router_traffic'}, {...base, source: 'parsed_only'},
    {...base, state: 'not_connected'}, {...base, state: 'stale'},
    {...base, state: 'otp_required'}, {...base, state: 'unauthorized'},
    {...base, state: 'unavailable'}, {...base, state: 'mystery'},
    {...base, remaining_bytes: -1}, {...base, remaining_bytes: 11 * 1024 ** 3},
    {...base, remaining_bytes: '500'}, {...base, total_bytes: 0},
    {...base, provider: '<img onerror=alert(1)>'},
    {...base, schema: 2}, null, {}
  ];
  for (const x of broken) {
    assert.doesNotMatch(summarizeOperatorQuota(x).value, /[0-9]\\s*(?:GiB|MiB)/);
  }
});

test('display does not sum overlapping quota buckets', () => {
  const x = summarizeOperatorQuota({
    ...base, buckets: [
      { remaining_bytes: 4 * 1024 ** 3 },
      { remaining_bytes: 9 * 1024 ** 3 }
    ]
  });
  assert.equal(x.value, '4.00 GiB');
});

test('provider strings cannot inject arbitrary markup', () => {
  const x = summarizeOperatorQuota({...base, provider: '__proto__'});
  assert.equal(x.value, 'Unavailable');
  assert.equal(x.provider, 'Operator');
});
