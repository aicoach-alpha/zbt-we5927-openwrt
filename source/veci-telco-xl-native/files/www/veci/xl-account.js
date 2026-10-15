import { VeciApi } from './js/lib/api.js';

// XL actions must never submit credentials over cleartext HTTP.
// Only the existing authenticated VeCI ubus session can invoke the RPC.
// No logging, persistent storage, background refresh or auto OTP requests.
const api = new VeciApi();
const $ = id => document.getElementById(id);
const secure = () => window.location.protocol === 'https:';
function message(text, error = false) {
  const node = $('xl-feedback');
  node.textContent = text;
  node.dataset.state = error ? 'error' : 'info';
}
async function action(name, body, button) {
  if (!secure()) throw new Error('HTTPS is required for XL account actions.');
  if (!api.sessionId) throw new Error('Sign in to VeCI on this tab first.');
  button.disabled = true;
  try {
    const result = await api.call('veci.xl', name, body, { timeout: 35000 });
    if (!result?.ok) throw new Error({
      https_only_required: 'The router still accepts insecure HTTP administration. XL sign-in is blocked.',
      operator_config_unavailable: 'Operator account integration credentials are not configured.',
      otp_cooldown: 'An OTP was recently requested. Please wait before retrying.',
      operator_otp_request_failed: 'The operator did not accept the OTP request.',
      otp_verification_failed: 'The operator did not verify this OTP.',
      account_profile_verification_failed: 'Account number could not be verified against the operator profile.',
      quota_refresh_failed: 'The operator did not return verified quota data.'
    }[result?.reason] || 'XL account operation could not be completed.');
    return result;
  } finally {
    button.disabled = false;
  }
}
async function status() {
  try {
    const info = await api.call('veci.xl', 'status', {}, { timeout: 5000 });
    $('xl-transport').textContent = info.https_only ? 'HTTPS-only' : 'HTTPS-only required';
    $('xl-credentials').textContent = info.operator_configured ? 'Configured' : 'Not configured';
    $('xl-session').textContent = info.session || 'Not connected';
    if (!secure() || !info.https_only || !info.operator_configured) {
      $('xl-start').disabled = true;
      $('xl-submit').disabled = true;
      $('xl-refresh').disabled = true;
      message('Login disabled until HTTPS-only router administration and authorized XL integration are configured.', true);
    } else {
      $('xl-start').disabled = false;
      $('xl-submit').disabled = false;
      $('xl-refresh').disabled = info.session !== 'verified';
    }
  } catch {
    message('XL account backend is not available. VeCI Core and SMS are unchanged.', true);
    $('xl-start').disabled = true;
    $('xl-submit').disabled = true;
    $('xl-refresh').disabled = true;
  }
}
async function init() {
  if (!secure()) {
    message('Use HTTPS to access VeCI before entering any number or OTP.', true);
    $('xl-start').disabled = true;
    $('xl-submit').disabled = true;
    $('xl-refresh').disabled = true;
    $('xl-number').disabled = true;
    $('xl-otp').disabled = true;
    return;
  }
  if (!api.sessionId || !(await api.validateSession())) {
    message('Sign in to VeCI first, then reopen XL Account in the same tab.', true);
    return;
  }
  $('xl-start').addEventListener('click', async () => {
    const number = $('xl-number').value.trim();
    if (!/^62[0-9]{8,13}$/.test(number)) {
      message('Enter the XL number starting with 62 (10–15 digits).', true);
      return;
    }
    try {
      await action('requestOtp', { number }, $('xl-start'));
      message('Operator OTP requested. Enter the received code below.');
    } catch (err) {
      message(err.message, true);
    } finally {
      $('xl-number').value = '';
      await status();
    }
  });
  $('xl-submit').addEventListener('click', async () => {
    const otp = $('xl-otp').value.trim();
    if (!/^[0-9]{4,8}$/.test(otp)) {
      message('Enter a valid 4–8 digit OTP.', true);
      return;
    }
    try {
      const result = await action('submitOtp', { otp }, $('xl-submit'));
      message(result.state === 'quota_refreshed'
        ? 'Account confirmed. Verified quota is available in the Cellular panel.'
        : 'Account confirmed, but the operator quota could not be retrieved.');
    } catch (err) {
      message(err.message, true);
    } finally {
      $('xl-otp').value = '';
      await status();
    }
  });
  $('xl-refresh').addEventListener('click', async () => {
    try {
      await action('refreshQuota', {}, $('xl-refresh'));
      message('Verified operator quota refreshed. Open Cellular to view it.');
    } catch (err) {
      message(err.message, true);
    } finally {
      await status();
    }
  });
  await status();
}
window.addEventListener('pagehide', () => {
  $('xl-number').value = '';
  $('xl-otp').value = '';
});
void init();
