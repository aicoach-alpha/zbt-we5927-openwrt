/* Native VeCI quota status view. Fail closed on unverified operator data. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.VeCIQuotaView = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const messages = Object.freeze({
    not_supported:'Operator belum didukung',
    authentication_required:'Login operator diperlukan',
    pending_otp:'Menunggu kode OTP',
    rate_limited:'Terlalu banyak permintaan. Coba lagi nanti',
    stale:'Informasi kuota kedaluwarsa',
    unavailable:'Kuota operator belum tersedia'
  });
  function failure(state) {
    const code = Object.hasOwn(messages,state) ? state : 'unavailable';
    return {state:code,message:messages[code],buckets:[]};
  }
  function bytes(n) {
    return (n / 1073741824).toFixed(2) + ' GB';
  }
  function model(data, clockMs) {
    const d = data && typeof data === 'object' && !Array.isArray(data) ? data : {};
    if (d.state !== 'ok' || d.source !== 'operator') return failure(d.state === 'ok' ? 'unavailable' : d.state);
    const now = Number.isFinite(clockMs) ? clockMs : Date.now();
    const fetched = typeof d.fetched_at === 'string' ? Date.parse(d.fetched_at) : NaN;
    if (!Number.isFinite(fetched) || fetched > now + 300000 || now - fetched > 3600000) {
      return failure('stale');
    }
    if (!Array.isArray(d.buckets) || d.buckets.length < 1 || d.buckets.length > 64) {
      return failure('unavailable');
    }
    const partial = d.quality === 'remaining_only';
    const buckets = [];
    for (const b of d.buckets) {
      if (!b || typeof b !== 'object' || Array.isArray(b) ||
          typeof b.label !== 'string' || !b.label.trim() || b.label.length > 100 ||
          !Number.isSafeInteger(b.remaining_bytes) || b.remaining_bytes < 0) {
        return failure('unavailable');
      }
      const hasTotal = Object.hasOwn(b,'total_bytes');
      const hasExpiry = Object.hasOwn(b,'expires_at');
      if ((!partial && (!hasTotal || !hasExpiry)) ||
          (hasTotal && (!Number.isSafeInteger(b.total_bytes) || b.total_bytes < b.remaining_bytes)) ||
          (hasExpiry && (typeof b.expires_at !== 'string' || !Number.isFinite(Date.parse(b.expires_at))))) {
        return failure('unavailable');
      }
      buckets.push({
        label:b.label,remaining:bytes(b.remaining_bytes),
        ...(hasTotal ? {total:bytes(b.total_bytes)} : {}),
        ...(hasExpiry ? {expires:new Date(b.expires_at).toLocaleString('id-ID',{timeZone:'Asia/Jakarta'})} : {})
      });
    }
    return {state:'ok',message:'Kuota operator',buckets};
  }
  function render(element, data) {
    if (!element || !element.ownerDocument) throw Error('missing mount element');
    const doc = element.ownerDocument, m = model(data);
    element.replaceChildren();
    const heading = doc.createElement('h3');
    heading.textContent = m.message;
    element.appendChild(heading);
    for (const b of m.buckets) {
      const article = doc.createElement('article');
      const lines = [b.label, b.total ? b.remaining + ' / ' + b.total : 'Sisa: ' + b.remaining];
      if (b.expires) lines.push('Berlaku sampai: ' + b.expires);
      for (const line of lines) {
        const p = doc.createElement('p');
        p.textContent = line;
        article.appendChild(p);
      }
      element.appendChild(article);
    }
  }
  return {model,render};
});
