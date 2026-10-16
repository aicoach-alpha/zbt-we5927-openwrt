// VeCI-only XL account handoff, not an authentication client.
// The official myXL page handles account login. This component never handles
// MSISDN, OTP, cookies, sessions, bearer tokens, or operator network requests.
const OFFICIAL_MYXL = 'https://www.xl.co.id/id/myxl';

export function xlAccountGuidance(status) {
  const provider = status?.provider === 'xl';
  if (!provider) return Object.freeze({
    available: false, url: null, label: 'No supported operator handoff'
  });
  return Object.freeze({
    available: true,
    url: OFFICIAL_MYXL,
    label: 'View quota in official myXL',
    explanation: status?.state === 'ready' &&
      status?.source === 'carrier_authenticated'
      ? 'The displayed balance is from the verified local carrier cache. myXL can show detailed package benefits.'
      : 'myXL provides account login and quota checks. Opening myXL does not connect the account to VeCI.'
  });
}

// Append only to the existing VeCI quota panel; no modifications to SMS/USSD.
export function mountXlAccountGuidance(panel, status) {
  if (!panel || typeof panel.querySelector !== 'function') return null;
  const guidance = xlAccountGuidance(status);
  const existing = panel.querySelector('[data-official-xl-guidance]');
  if (!guidance.available) {
    if (existing) existing.remove();
    return null;
  }
  if (existing) return existing;
  const box = document.createElement('div');
  box.setAttribute('data-official-xl-guidance', 'true');
  box.className = 'cellular-actions';
  const a = document.createElement('a');
  a.className = 'button button-secondary';
  a.textContent = guidance.label;
  a.href = OFFICIAL_MYXL;
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  a.referrerPolicy = 'no-referrer';
  const caption = document.createElement('p');
  caption.className = 'panel-copy';
  caption.textContent = guidance.explanation;
  box.append(a, caption);
  panel.appendChild(box);
  return box;
}
