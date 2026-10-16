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
  // Formatted values are accepted only when the authenticated backend has
  // independently verified the operator's byte-unit convention. EnQuota's
  // XL fallback can synthesize "0 MB" for an absent field, so never parse
  // display strings on a caller's success flag alone.
  function displayBytes(value) {
    const match = typeof value === 'string' &&
      /^(0|[1-9][0-9]{0,11})(?:[.,]([0-9]{1,3}))? (B|KB|MB|GB)$/i.exec(value.trim());
    if (!match) return null;
    const scale = {B:1,KB:1024,MB:1048576,GB:1073741824}[match[3].toUpperCase()];
    const decimals = match[2] || '';
    const numerator = Number(match[1]) * 10 ** decimals.length + Number(decimals || 0);
    const bytes = numerator * scale / 10 ** decimals.length;
    return Number.isSafeInteger(bytes) && bytes >= 0 ? bytes : null;
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
      let remaining = toBytes(item,'remaining');
      const total = toBytes(item,'total');
      // Optional display-only figures must have independently verified units.
      if (remaining === null && evidence.remaining_units_verified === true &&
          evidence.remaining_field_present === true)
        remaining = displayBytes(item.remainingFormatted);
      if (remaining === null || (total !== null && remaining > total))
        return failure(operator,'unavailable');
      const expiry = item.validUntil;
      const expiryKnown = typeof expiry === 'string' && expiry !== '-';
      if (expiryKnown && !Number.isFinite(Date.parse(expiry)))
        return failure(operator,'unavailable');
      const bucket = {label:item.name, remaining_bytes:remaining};
      if (total !== null) bucket.total_bytes = total;
      if (expiryKnown) bucket.expires_at = new Date(expiry).toISOString();
      buckets.push(bucket);
    }
    const partial = buckets.some(b => !Object.hasOwn(b,'total_bytes') || !Object.hasOwn(b,'expires_at'));
    return {operator, state:'ok',source:'operator',
      ...(partial ? {quality:'remaining_only'} : {}),
      fetched_at:new Date(evidence.fetched_at).toISOString(), buckets};
  }
  return {convert};
});
