/**
 * VeCI native Settings > Network > IPv6.
 * UI adapter ONLY: privileged backend must implement authenticated
 * status / preflight / explicit apply with rollback. No shell/UCI in browser.
 * Never claim a change succeeded merely because a request was accepted.
 */
export async function mountIPv6Settings(host, api) {
  if (!host || typeof host.replaceChildren !== 'function')
    throw new TypeError('settings_host_required');
  const doc = host.ownerDocument;
  const panel = doc.createElement('section');
  panel.className = 'veci-ipv6-control';
  const title = doc.createElement('h3');
  title.textContent = 'IPv6';
  const details = doc.createElement('p');
  details.textContent = 'Checking IPv6 status…';
  const control = doc.createElement('button');
  control.type = 'button';
  control.disabled = true;
  control.textContent = 'Unavailable';
  panel.append(title, details, control);
  host.replaceChildren(panel);
  if (!api || typeof api.status !== 'function' ||
      typeof api.preflight !== 'function' || typeof api.setEnabled !== 'function') {
    details.textContent = 'IPv6 settings unavailable until the native VeCI backend is installed.';
    return {status:'backend_missing'};
  }
  let current;
  try {
    current = await api.status();
    if (!current || current.supported !== true ||
        typeof current.enabled !== 'boolean') throw Error('unsupported');
    details.textContent = current.enabled ?
      'IPv6 is enabled. IPv4 remains available.' :
      'IPv6 is OFF. IPv4 is the primary connection.';
    control.textContent = current.enabled ? 'Disable IPv6' : 'Enable IPv6';
    control.disabled = false;
  } catch {
    details.textContent = 'Cannot verify IPv6 state; no settings were changed.';
    return {status:'status_unavailable'};
  }
  control.onclick = async () => {
    control.disabled = true;
    const target = !current.enabled;
    try {
      const check = await api.preflight(target);
      if (!check || check.safe !== true) {
        details.textContent = 'Blocked: ' + String(check?.reason || 'safety_preflight_failed');
        return;
      }
      const prompt = target
        ? 'Enable IPv6? This can change routing and may require a scheduled maintenance window.'
        : 'Disable IPv6? This can break IPv4 on DS-Lite/464XLAT networks.';
      if (!doc.defaultView?.confirm(prompt)) return;
      const result = await api.setEnabled(target);
      // Re-read effective state; queued/saved config is not operational success.
      if (!result || result.ok !== true) throw Error('apply_failed');
      const next = await api.status();
      if (next?.enabled === target && next?.effective === true) {
        current = next;
        details.textContent = target ? 'IPv6 enabled and verified.' : 'IPv6 disabled and verified.';
        control.textContent = target ? 'Disable IPv6' : 'Enable IPv6';
      } else {
        details.textContent = 'Change pending verification; active routing state not confirmed.';
      }
    } catch {
      details.textContent = 'IPv6 change failed or verification unavailable; check router status.';
    } finally {
      control.disabled = false;
    }
  };
  return {status:'ready'};
}
