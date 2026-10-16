/* Native VeCI quota status view. Does not modify LuCI or access operator APIs. */
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
  function bytes(n) {
    if (!Number.isSafeInteger(n) || n < 0) throw Error('invalid bytes');
    return (n / 1073741824).toFixed(2) + ' GB';
  }
  function model(data) {
    const d = data && typeof data === 'object' ? data : {};
    if (d.state !== 'ok' || d.source !== 'operator' || !Array.isArray(d.buckets)) {
      return {state: messages[d.state] ? d.state : 'unavailable', message:messages[d.state] || messages.unavailable,buckets:[]};
    }
    return {state:'ok', message:'Kuota operator', buckets:d.buckets.map(b=>({
      label:String(b.label), remaining:bytes(b.remaining_bytes),
      ...(Number.isSafeInteger(b.total_bytes) ? {total:bytes(b.total_bytes)} : {}),
      ...(typeof b.expires_at === 'string' && Number.isFinite(Date.parse(b.expires_at))
        ? {expires:new Date(b.expires_at).toLocaleString('id-ID',{timeZone:'Asia/Jakarta'})} : {})
    }))};
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
        p.textContent = line; // Never use innerHTML for provider-supplied labels.
        article.appendChild(p);
      }
      element.appendChild(article);
    }
  }
  return {model,render};
});
