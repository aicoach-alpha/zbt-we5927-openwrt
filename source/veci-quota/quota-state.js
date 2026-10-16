/* VeCI quota state contract. No provider credentials or network requests. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.VeCIQuotaState = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const ERRORS = ['not_supported', 'authentication_required', 'pending_otp',
    'rate_limited', 'stale', 'unavailable'];
  function normalize(input, nowMs) {
    const now = Number.isFinite(nowMs) ? nowMs : Date.now();
    const obj = input && typeof input === 'object' && !Array.isArray(input) ? input : {};
    const state = typeof obj.state === 'string' ? obj.state : 'unavailable';
    const operator = typeof obj.operator === 'string' && /^[a-z0-9_-]{1,32}$/.test(obj.operator) ? obj.operator : 'unknown';
    const base = { operator, state: ERRORS.includes(state) ? state : 'unavailable', buckets: [] };
    if (state !== 'ok' || obj.source !== 'operator') return base;
    const fetched = Date.parse(obj.fetched_at);
    if (!Number.isFinite(fetched) || fetched > now + 300000 || now - fetched > 3600000) {
      base.state = 'stale';
      return base;
    }
    if (!Array.isArray(obj.buckets) || !obj.buckets.length || obj.buckets.length > 64) return base;
    const buckets = [];
    for (const b of obj.buckets) {
      if (!b || typeof b !== 'object') return base;
      if (typeof b.label !== 'string' || !b.label.trim() || b.label.length > 100) return base;
      if (!Number.isSafeInteger(b.remaining_bytes) || b.remaining_bytes < 0) return base;
      if (!Number.isSafeInteger(b.total_bytes) || b.total_bytes < b.remaining_bytes) return base;
      const expiry = Date.parse(b.expires_at);
      if (!Number.isFinite(expiry)) return base;
      buckets.push({label: b.label, remaining_bytes: b.remaining_bytes,
        total_bytes: b.total_bytes, expires_at: new Date(expiry).toISOString()});
    }
    return {operator, state: 'ok', source: 'operator',
      fetched_at: new Date(fetched).toISOString(), buckets};
  }
  return { normalize };
});
