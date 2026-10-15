// VeCI-only additive operator quota panel.
// Read-only veci.quota.status; no OTP, modem, SMS, USSD, or external network request.
// Designed to preserve the deployed Cellular/SMS Center implementation unmodified.
const PROVIDERS = Object.freeze({
  xl: 'XL', axis: 'AXIS', smartfren: 'Smartfren',
  telkomsel: 'Telkomsel', byu: 'by.U',
  im3: 'IM3', tri: 'Tri', orbit: 'Telkomsel Orbit'
});

const safeBytes = n => Number.isSafeInteger(n) && n >= 0;

function humanBytes(n) {
  return n >= 1024 ** 3
    ? (n / 1024 ** 3).toFixed(2) + ' GiB'
    : (n / 1024 ** 2).toFixed(1) + ' MiB';
}

export function summarizeOperatorQuota(payload) {
  const unavailable = { provider: 'Operator', value: 'Unavailable', detail: 'Verified operator quota is not available.' };
  if (!payload || payload.schema !== 1 ||
      !Object.prototype.hasOwnProperty.call(PROVIDERS, payload.provider)) return unavailable;
  const provider = PROVIDERS[payload.provider];
  const status = { provider, value: 'Unavailable', detail: 'Verified operator quota is not available.' };
  switch (payload.state) {
    case 'not_connected':
      return { provider, value: 'Not connected', detail: 'Operator account authentication is not configured.' };
    case 'otp_required':
    case 'unauthorized':
      return { provider, value: 'Sign-in required', detail: 'Operator account authentication is required.' };
    case 'stale':
      return { provider, value: 'Expired', detail: 'Operator quota data is stale; no balance is shown.' };
    case 'unavailable':
      return status;
    case 'ready':
      break;
    default:
      return status;
  }
  if (payload.source !== 'carrier_authenticated' ||
      !safeBytes(payload.remaining_bytes) ||
      !safeBytes(payload.total_bytes) || payload.total_bytes === 0 ||
      payload.remaining_bytes > payload.total_bytes) return status;
  return {
    provider,
    value: humanBytes(payload.remaining_bytes),
    detail: 'Remaining of ' + humanBytes(payload.total_bytes) + ' · Verified operator result'
  };
}

export function mountOperatorQuota({ api, root }) {
  if (!root || !api || root.querySelector('#cellular-operator-quota-panel')) return;
  const section = document.createElement('section');
  section.id = 'cellular-operator-quota-panel';
  section.className = 'panel';
  section.innerHTML = `
    <div class="panel-heading">
      <div><p class="eyebrow">INDONESIA · OPERATOR</p><h3>Operator Data Quota</h3></div>
    </div>
    <div class="detail-list">
      <div><span>Operator</span><strong data-quota-provider>Checking…</strong></div>
      <div><span>Remaining quota / status</span><strong data-quota-value>Checking…</strong></div>
      <div><span>Information</span><strong data-quota-detail>Local read-only status</strong></div>
    </div>
    <p class="panel-copy">Operator quota is separate from router traffic usage. Only an authenticated operator response can show a balance.</p>
    <div class="cellular-actions">
      <button type="button" class="button button-secondary" data-quota-refresh>Refresh local quota status</button>
    </div>`;
  const smsSection = root.querySelector('section[aria-labelledby="cellular-sms-mifi-title"]');
  if (smsSection) smsSection.before(section);
  else root.appendChild(section);
  const button = section.querySelector('[data-quota-refresh]');
  const provider = section.querySelector('[data-quota-provider]');
  const value = section.querySelector('[data-quota-value]');
  const detail = section.querySelector('[data-quota-detail]');
  async function refresh() {
    if (button.disabled) return;
    button.disabled = true;
    button.textContent = 'Refreshing…';
    try {
      const summary = summarizeOperatorQuota(
        await api.call('veci.quota', 'status', {}, { timeout: 2500 })
      );
      if (!root.contains(section)) return;
      provider.textContent = summary.provider;
      value.textContent = summary.value;
      detail.textContent = summary.detail;
    } catch {
      if (!root.contains(section)) return;
      provider.textContent = 'Operator';
      value.textContent = 'Unavailable';
      detail.textContent = 'Cannot read local quota status; no operator request was sent.';
    } finally {
      button.disabled = false;
      button.textContent = 'Refresh local quota status';
    }
  }
  button.addEventListener('click', refresh);
  void refresh();
  return section;
}
