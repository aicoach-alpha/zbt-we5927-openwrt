/* Convert EnQuota's documented QuotaResult shape to VeCI's source-verified
 * quota contract. This module is transport-agnostic: no API calls or secrets.
 * Never trust a caller's success alone as evidence of operator provenance.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.VeCIEnQuotaAdapter = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const names = Object.freeze({XL:'xl', AXIS:'axis', TRI:'tri',
    INDOSAT:'indosat', TELKOMSEL:'telkomsel', BYU:'byu'});
  function failure(operator, state) {
    return {operator, state, buckets:[]};
  }
  function toBytes(item, field) {
    const bytes = item[field + 'Bytes'];
    if (Number.isSafeInteger(bytes) && bytes >= 0) return bytes;
    const mb = item[field + 'Mb'], gb = item[field + 'Gb'];
    const n = Number.isFinite(mb) ? mb * 1048576 :
      Number.isFinite(gb) ? gb * 1073741824 : NaN;
    return Number.isSafeInteger(n) && n >= 0 ? n : null;
  }
  function convert(result, evidence) {
    const operator = names[String(result && result.provider || '').toUpperCase()] || 'unknown';
    // EnQuota can return formatted text such as '1 GB' without numerical balance.
    // It is not safe to infer a complete operator bucket from that string.
    if (!evidence || evidence.authoritative !== true || evidence.authenticated !== true)
      return failure(operator,'authentication_required');
    if (!result || result.success !== true || !Array.isArray(result.items) ||
        !result.items.length) return failure(operator,'unavailable');
    if (!Number.isFinite(Date.parse(evidence.fetched_at))) return failure(operator,'unavailable');
    const buckets = [];
    for (const item of result.items) {
      if (!item || typeof item.name !== 'string' || !item.name.trim()) return failure(operator,'unavailable');
      const remaining = toBytes(item,'remaining');
      const total = toBytes(item,'total');
      // EnQuota QuotaItem defines totalBytes but it is optional.
      // No fabricated total or default expiration is permitted.
      const expiry = item.validUntil;
      if (remaining === null || total === null || remaining > total ||
          typeof expiry !== 'string' || !Number.isFinite(Date.parse(expiry)))
        return failure(operator,'unavailable');
      buckets.push({label:item.name, remaining_bytes:remaining, total_bytes:total,
        expires_at:new Date(expiry).toISOString()});
    }
    return {operator, state:'ok',source:'operator',
      fetched_at:new Date(evidence.fetched_at).toISOString(), buckets};
  }
  return {convert};
});
